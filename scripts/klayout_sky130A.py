# Run by the desktop's KLayout icon (scripts/desktop/install_desktop.sh) as
#   klayout -e -rm /foss/designs/scripts/klayout_sky130A.py
# Makes sky130A the technology that File > Open applies, so a GDS opened from
# the File menu shows sky130's layer names and colours.
#
# KLayout takes that technology from its initial-technology setting, which the
# image's /headless/.klayout/klayoutrc sets to sg13g2. That IHP technology is
# not on KLAYOUT_PATH once .designinit has switched to sky130A, so KLayout
# falls back to its default technology and shows bare layer numbers.
# klayout -n sky130A does not help here: it applies only to files named on the
# command line, and the icon names none.
import pya

pya.Application.instance().set_config("initial-technology", "sky130A")
