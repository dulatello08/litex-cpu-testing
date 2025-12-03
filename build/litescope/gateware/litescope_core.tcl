prj_project new -name "litescope_core" -impl "impl" -dev LFE5U-85F -synthesis "synplify"
prj_impl option {include path} {""}
prj_src add "/Users/dulat/Documents/cpu/litex-testing/build/litescope/gateware/litescope_core.v" -work work
prj_impl option top "litescope_core"
prj_project save
prj_run Synthesis -impl impl -forceOne
prj_run Translate -impl impl
prj_run Map -impl impl
prj_run PAR -impl impl
prj_run Export -impl impl -task Bitgen
prj_project close