#!/usr/bin/env python3
"""
LCSC Linker GUI - wxPython GUI for linking KiCad components to LCSC parts.
"""

import sys
import threading
import webbrowser
from pathlib import Path

import wx
import wx.lib.mixins.listctrl as listmix

from kicad_parser import KicadSchParser, Component
from lcsc_api import LCSCClient, LCSCComponent, build_search_query


class ComponentListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """Component list with auto-width columns."""

    def __init__(self, parent):
        wx.ListCtrl.__init__(
            self, parent,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        listmix.ListCtrlAutoWidthMixin.__init__(self)

        self.InsertColumn(0, "Reference", width=80)
        self.InsertColumn(1, "Value", width=120)
        self.InsertColumn(2, "Footprint", width=180)
        self.InsertColumn(3, "LCSC", width=100)
        self.InsertColumn(4, "Status", width=80)

        self.setResizeColumn(3)


class SearchResultListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """Search result list with auto-width columns."""

    def __init__(self, parent):
        wx.ListCtrl.__init__(
            self, parent,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        listmix.ListCtrlAutoWidthMixin.__init__(self)

        self.InsertColumn(0, "LCSC ID", width=90)
        self.InsertColumn(1, "Manufacturer", width=120)
        self.InsertColumn(2, "Part Number", width=150)
        self.InsertColumn(3, "Package", width=80)
        self.InsertColumn(4, "Stock", width=70)
        self.InsertColumn(5, "Price", width=70)

        self.setResizeColumn(3)


class ComponentDialog(wx.Dialog):
    """Dialog for selecting LCSC component for a schematic component."""

    def __init__(self, parent, component: Component, client: LCSCClient):
        super().__init__(
            parent,
            title=f"Select LCSC Part - {component.reference}",
            size=(800, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        self.component = component
        self.client = client
        self.search_results: list[LCSCComponent] = []
        self.selected_lcsc_id = ""
        self.selected_url = ""

        self._init_ui()
        self._do_initial_search()

    def _init_ui(self):
        """Initialize the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Component info
        info_box = wx.StaticBox(panel, label="Component Information")
        info_sizer = wx.StaticBoxSizer(info_box, wx.VERTICAL)

        grid = wx.FlexGridSizer(4, 2, 5, 10)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(panel, label="Reference:"), 0, wx.ALIGN_RIGHT)
        grid.Add(wx.StaticText(panel, label=self.component.reference), 0, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="Value:"), 0, wx.ALIGN_RIGHT)
        grid.Add(wx.StaticText(panel, label=self.component.value), 0, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="Footprint:"), 0, wx.ALIGN_RIGHT)
        grid.Add(wx.StaticText(panel, label=self.component.footprint), 0, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="Current LCSC:"), 0, wx.ALIGN_RIGHT)
        current_lcsc = self.component.lcsc if self.component.lcsc else "(none)"
        grid.Add(wx.StaticText(panel, label=current_lcsc), 0, wx.EXPAND)

        info_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Search controls
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_sizer.Add(wx.StaticText(panel, label="Search:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.search_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        search_sizer.Add(self.search_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)

        search_btn = wx.Button(panel, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self._on_search)
        search_sizer.Add(search_btn, 0)

        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Results list
        self.result_list = SearchResultListCtrl(panel)
        self.result_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_activated)
        self.result_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_item_selected)
        main_sizer.Add(self.result_list, 1, wx.EXPAND | wx.ALL, 10)

        # Status
        self.status_text = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Manual entry
        manual_sizer = wx.BoxSizer(wx.HORIZONTAL)
        manual_sizer.Add(wx.StaticText(panel, label="Manual LCSC ID:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.manual_ctrl = wx.TextCtrl(panel, size=(120, -1))
        self.manual_ctrl.SetHint("C123456")
        manual_sizer.Add(self.manual_ctrl, 0, wx.RIGHT, 5)

        manual_btn = wx.Button(panel, label="Use Manual ID")
        manual_btn.Bind(wx.EVT_BUTTON, self._on_manual_entry)
        manual_sizer.Add(manual_btn, 0)

        main_sizer.Add(manual_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        select_btn = wx.Button(panel, wx.ID_OK, label="Select")
        select_btn.Bind(wx.EVT_BUTTON, self._on_select)
        btn_sizer.Add(select_btn, 0, wx.RIGHT, 5)

        skip_btn = wx.Button(panel, label="Skip")
        skip_btn.Bind(wx.EVT_BUTTON, self._on_skip)
        btn_sizer.Add(skip_btn, 0, wx.RIGHT, 5)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel All")
        btn_sizer.Add(cancel_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(main_sizer)

    def _do_initial_search(self):
        """Perform initial search based on component value and footprint."""
        query = build_search_query(self.component.value, self.component.footprint)
        self.search_ctrl.SetValue(query)
        self._perform_search(query)

    def _on_search(self, event):
        """Handle search button click."""
        query = self.search_ctrl.GetValue().strip()
        if query:
            self._perform_search(query)

    def _perform_search(self, query: str):
        """Perform search and update results."""
        self.status_text.SetLabel(f"Searching for '{query}'...")
        self.result_list.DeleteAllItems()
        wx.GetApp().Yield()

        try:
            self.search_results = self.client.search(query, limit=15)
            self._update_results()
        except Exception as e:
            self.status_text.SetLabel(f"Search error: {e}")

    def _update_results(self):
        """Update the results list."""
        self.result_list.DeleteAllItems()

        if not self.search_results:
            self.status_text.SetLabel("No results found. Try a different search query.")
            return

        for i, comp in enumerate(self.search_results):
            idx = self.result_list.InsertItem(i, comp.lcsc_id)
            self.result_list.SetItem(idx, 1, comp.manufacturer or "-")
            self.result_list.SetItem(idx, 2, comp.mfr_part or "-")
            self.result_list.SetItem(idx, 3, comp.package or "-")
            self.result_list.SetItem(idx, 4, str(comp.stock) if comp.stock else "-")
            self.result_list.SetItem(idx, 5, f"${comp.price:.4f}" if comp.price else "-")

        self.status_text.SetLabel(f"Found {len(self.search_results)} results. Double-click or select and click 'Select'.")

    def _on_item_selected(self, event):
        """Handle item selection."""
        idx = event.GetIndex()
        if 0 <= idx < len(self.search_results):
            comp = self.search_results[idx]
            self.selected_lcsc_id = comp.lcsc_id
            self.selected_url = comp.url

    def _on_item_activated(self, event):
        """Handle item double-click - open URL in browser."""
        idx = event.GetIndex()
        if 0 <= idx < len(self.search_results):
            comp = self.search_results[idx]
            webbrowser.open(comp.url)

    def _on_select(self, event):
        """Handle select button click."""
        if self.selected_lcsc_id:
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Please select a component from the list.", "No Selection", wx.OK | wx.ICON_WARNING)

    def _on_skip(self, event):
        """Handle skip button click."""
        self.selected_lcsc_id = ""
        self.selected_url = ""
        self.EndModal(wx.ID_NO)

    def _on_manual_entry(self, event):
        """Handle manual LCSC ID entry."""
        lcsc_id = self.manual_ctrl.GetValue().strip().upper()
        if lcsc_id and lcsc_id.startswith('C') and lcsc_id[1:].isdigit():
            self.selected_lcsc_id = lcsc_id
            self.selected_url = f"https://www.lcsc.com/product-detail/{lcsc_id}.html"
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Invalid LCSC ID. Must be like 'C123456'.", "Invalid ID", wx.OK | wx.ICON_ERROR)


class MainFrame(wx.Frame):
    """Main application window."""

    def __init__(self):
        super().__init__(
            None,
            title="LCSC Linker for KiCad",
            size=(900, 600)
        )

        self.parser: KicadSchParser = None
        self.components: list[Component] = []
        self.client = LCSCClient()
        self.current_file = None

        self._init_ui()
        self._init_menu()
        self.Centre()

    def _init_ui(self):
        """Initialize the main UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # File selection
        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_sizer.Add(wx.StaticText(panel, label="Schematic:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.file_ctrl = wx.TextCtrl(panel, style=wx.TE_READONLY)
        file_sizer.Add(self.file_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)

        browse_btn = wx.Button(panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        file_sizer.Add(browse_btn, 0)

        main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Component list
        self.comp_list = ComponentListCtrl(panel)
        self.comp_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_component_activated)
        main_sizer.Add(self.comp_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Status bar info
        self.status_label = wx.StaticText(panel, label="Open a .kicad_sch file to begin.")
        main_sizer.Add(self.status_label, 0, wx.EXPAND | wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.process_btn = wx.Button(panel, label="Process All Components")
        self.process_btn.Bind(wx.EVT_BUTTON, self._on_process_all)
        self.process_btn.Enable(False)
        btn_sizer.Add(self.process_btn, 0, wx.RIGHT, 5)

        self.process_empty_btn = wx.Button(panel, label="Process Empty Only")
        self.process_empty_btn.Bind(wx.EVT_BUTTON, self._on_process_empty)
        self.process_empty_btn.Enable(False)
        btn_sizer.Add(self.process_empty_btn, 0, wx.RIGHT, 5)

        self.save_btn = wx.Button(panel, label="Save")
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        self.save_btn.Enable(False)
        btn_sizer.Add(self.save_btn, 0, wx.RIGHT, 5)

        self.open_urls_btn = wx.Button(panel, label="Open All URLs")
        self.open_urls_btn.Bind(wx.EVT_BUTTON, self._on_open_all_urls)
        self.open_urls_btn.Enable(False)
        btn_sizer.Add(self.open_urls_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")

    def _init_menu(self):
        """Initialize the menu bar."""
        menubar = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, "&Open\tCtrl+O", "Open schematic file")
        save_item = file_menu.Append(wx.ID_SAVE, "&Save\tCtrl+S", "Save schematic file")
        save_as_item = file_menu.Append(wx.ID_SAVEAS, "Save &As...", "Save schematic as new file")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl+Q", "Exit application")

        self.Bind(wx.EVT_MENU, self._on_open, open_item)
        self.Bind(wx.EVT_MENU, self._on_save, save_item)
        self.Bind(wx.EVT_MENU, self._on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self._on_exit, exit_item)

        menubar.Append(file_menu, "&File")

        # Help menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About LCSC Linker")
        self.Bind(wx.EVT_MENU, self._on_about, about_item)

        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

    def _on_browse(self, event):
        """Handle browse button click."""
        with wx.FileDialog(
            self,
            "Open KiCad Schematic",
            wildcard="KiCad Schematic (*.kicad_sch)|*.kicad_sch",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self._load_file(dialog.GetPath())

    def _on_open(self, event):
        """Handle File > Open."""
        self._on_browse(event)

    def _load_file(self, filepath: str):
        """Load a schematic file."""
        try:
            self.parser = KicadSchParser(filepath)
            self.components = self.parser.parse()
            self.current_file = filepath

            self.file_ctrl.SetValue(filepath)
            self._update_component_list()

            self.process_btn.Enable(len(self.components) > 0)
            self.process_empty_btn.Enable(len(self.components) > 0)
            self.save_btn.Enable(False)

            linked_count = sum(1 for c in self.components if c.lcsc)
            self.open_urls_btn.Enable(linked_count > 0)

            empty_count = sum(1 for c in self.components if not c.lcsc)
            self.status_label.SetLabel(
                f"Loaded {len(self.components)} components. "
                f"{empty_count} without LCSC ID."
            )
            self.SetStatusText(f"Loaded: {filepath}")

        except Exception as e:
            wx.MessageBox(f"Error loading file:\n{e}", "Error", wx.OK | wx.ICON_ERROR)

    def _update_component_list(self):
        """Update the component list display."""
        self.comp_list.DeleteAllItems()

        for i, comp in enumerate(self.components):
            idx = self.comp_list.InsertItem(i, comp.reference)
            self.comp_list.SetItem(idx, 1, comp.value)
            self.comp_list.SetItem(idx, 2, comp.footprint)
            self.comp_list.SetItem(idx, 3, comp.lcsc or "")
            status = "Linked" if comp.lcsc else "Empty"
            self.comp_list.SetItem(idx, 4, status)

    def _on_component_activated(self, event):
        """Handle component double-click."""
        idx = event.GetIndex()
        if 0 <= idx < len(self.components):
            self._process_single_component(idx)

    def _process_single_component(self, idx: int):
        """Process a single component."""
        comp = self.components[idx]
        dlg = ComponentDialog(self, comp, self.client)
        result = dlg.ShowModal()

        if result == wx.ID_OK and dlg.selected_lcsc_id:
            self.parser.update_component(comp, dlg.selected_lcsc_id, dlg.selected_url)
            self._update_component_list()
            self.save_btn.Enable(True)
            linked_count = sum(1 for c in self.components if c.lcsc)
            self.open_urls_btn.Enable(linked_count > 0)
            self.SetStatusText(f"Updated {comp.reference} with {dlg.selected_lcsc_id}")

        dlg.Destroy()

    def _on_process_all(self, event):
        """Process all components."""
        self._process_components(self.components)

    def _on_process_empty(self, event):
        """Process only components without LCSC."""
        empty_comps = [c for c in self.components if not c.lcsc]
        if not empty_comps:
            wx.MessageBox("All components already have LCSC IDs.", "Info", wx.OK | wx.ICON_INFORMATION)
            return
        self._process_components(empty_comps)

    def _process_components(self, components: list[Component]):
        """Process a list of components interactively."""
        updated = 0
        skipped = 0

        for i, comp in enumerate(components):
            dlg = ComponentDialog(self, comp, self.client)
            dlg.SetTitle(f"[{i+1}/{len(components)}] Select LCSC Part - {comp.reference}")
            result = dlg.ShowModal()

            if result == wx.ID_CANCEL:
                dlg.Destroy()
                break
            elif result == wx.ID_OK and dlg.selected_lcsc_id:
                self.parser.update_component(comp, dlg.selected_lcsc_id, dlg.selected_url)
                updated += 1
            else:
                skipped += 1

            dlg.Destroy()

        self._update_component_list()
        if updated > 0:
            self.save_btn.Enable(True)
            linked_count = sum(1 for c in self.components if c.lcsc)
            self.open_urls_btn.Enable(linked_count > 0)

        wx.MessageBox(
            f"Processing complete.\n\nUpdated: {updated}\nSkipped: {skipped}",
            "Complete",
            wx.OK | wx.ICON_INFORMATION
        )

    def _on_save(self, event):
        """Save the schematic."""
        if self.parser and self.current_file:
            try:
                self.parser.save()
                self.save_btn.Enable(False)
                self.SetStatusText(f"Saved: {self.current_file}")
                wx.MessageBox("Schematic saved successfully.", "Saved", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"Error saving file:\n{e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_save_as(self, event):
        """Save the schematic as a new file."""
        if not self.parser:
            return

        with wx.FileDialog(
            self,
            "Save KiCad Schematic As",
            wildcard="KiCad Schematic (*.kicad_sch)|*.kicad_sch",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                try:
                    self.parser.save(dialog.GetPath())
                    self.current_file = dialog.GetPath()
                    self.file_ctrl.SetValue(dialog.GetPath())
                    self.save_btn.Enable(False)
                    self.SetStatusText(f"Saved: {dialog.GetPath()}")
                except Exception as e:
                    wx.MessageBox(f"Error saving file:\n{e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_open_all_urls(self, event):
        """Open all LCSC URLs in the default browser."""
        urls = []
        for comp in self.components:
            if comp.lcsc:
                url = comp.url if comp.url else f"https://www.lcsc.com/product-detail/{comp.lcsc}.html"
                urls.append(url)

        if not urls:
            wx.MessageBox("No components with LCSC IDs found.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        result = wx.MessageBox(
            f"Open {len(urls)} URLs in your browser?",
            "Confirm",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if result == wx.YES:
            for url in urls:
                webbrowser.open(url)
            self.SetStatusText(f"Opened {len(urls)} URLs")

    def _on_exit(self, event):
        """Exit the application."""
        self.Close()

    def _on_about(self, event):
        """Show about dialog."""
        info = wx.adv.AboutDialogInfo()
        info.SetName("LCSC Linker")
        info.SetVersion("1.0.0")
        info.SetDescription(
            "Link KiCad schematic components to LCSC parts.\n\n"
            "Search and select LCSC components for your KiCad schematics."
        )
        info.SetCopyright("(C) 2025")
        wx.adv.AboutBox(info)


def main():
    app = wx.App()
    frame = MainFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
