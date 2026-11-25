# Run by smoke_test.sh as:
#   QT_QPA_PLATFORM=offscreen klayout -z -nc -r scripts/klayout_check.py
# -z gives KLayout a hidden main window, which the plugin needs for its Magic
# menu; under -zz or -b KLayout has no main window. The offscreen platform lets
# it run without a display. The script prints the technologies, the libraries
# and the Magic menu's entries, one per line, then builds a
# sky130_fd_pr__nfet_01v8 PCell from the plugin's sky130_magic library. The
# plugin asks Magic for that cell.
import pya

for name in pya.Technology.technology_names():
    print("TECH " + name)
for name in pya.Library.library_names():
    print("LIB " + name)

app = pya.Application.instance()
mw = app.main_window() if app is not None else None
if mw is not None and mw.menu().is_menu("kmp_magic_menu"):
    menu = mw.menu()
    print("MENU " + menu.action("kmp_magic_menu").title)
    for item in menu.items("kmp_magic_menu"):
        title = menu.action(item).title
        if title:
            print("MENUITEM " + title)

if pya.Library.library_by_name("sky130_magic") is not None:
    layout = pya.Layout()
    cell = layout.create_cell("sky130_fd_pr__nfet_01v8", "sky130_magic", {})
    if cell is not None and not cell.bbox().empty():
        print("PCELL sky130_fd_pr__nfet_01v8 %s" % cell.dbbox())
    else:
        print("PCELL none")
