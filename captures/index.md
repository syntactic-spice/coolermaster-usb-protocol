# Capture index

USBPcap on the root hub holding the dongle (`2516:01B7`), filtered to the
dongle, descriptors injected. Mouse over 2.4 GHz, profile 0 active, MasterPlus+
196.0341.0412. Each file contains exactly one UI action, driven by script.
`tools/decode.py <file>` prints the vendor-interface reports.

| File | Action |
|---|---|
| `00_masterplus_startup` | MasterPlus launched; reads everything, cycles active profile 0→4→0 |
| `10_wireless_sleep_5m_to_10m` | Sleep timer 5 → 10 min |
| `11_wireless_sleep_10m_to_5m` | Sleep timer 10 → 5 min |
| `12_wireless_sleep_5m_to_1m` | Sleep timer 5 → 1 min |
| `13_wireless_sleep_1m_to_never` | Sleep timer 1 min → never |
| `14_wireless_sleep_never_to_5m` | Sleep timer never → 5 min |
| `15_wireless_lowpower_15_to_25` | Low-power threshold 15 → 25 % |
| `16_wireless_lowpower_25_to_95` | Low-power threshold 25 → 95 % |
| `17_wireless_lowpower_95_to_15` | Low-power threshold 95 → 15 % |
| `20_perf_polling_1000_to_500` | Polling 1000 → 500 Hz (also contains the stage 2 Y=0 MasterPlus bug) |
| `21_perf_polling_500_to_250` | Polling 500 → 250 Hz |
| `22_perf_polling_250_to_125` | Polling 250 → 125 Hz |
| `23_perf_polling_125_to_1000` | Polling 125 → 1000 Hz |
| `24_perf_anglesnap_off_to_on` | Angle snapping on |
| `25_perf_anglesnap_on_to_off` | Angle snapping off |
| `26_perf_lod_low_to_high` | Lift-off distance high |
| `27_perf_lod_high_to_low` | Lift-off distance low |
| `30_dpi_select_stage4_to_stage2` | Active DPI stage 4 → 2 (also fixes stage 2 Y) |
| `31_dpi_select_stage2_to_stage4` | Active DPI stage 2 → 4 |
| `32_dpi_enable_stage3` | Enable DPI stage 3 |
| `33_dpi_disable_stage3` | Disable DPI stage 3 |
| `34_perf_debounce_3ms_to_4ms` | Button response 3 → 4 ms |
| `35_perf_debounce_4ms_to_1ms` | Button response 4 → 1 ms |
| `36_perf_debounce_1ms_to_6ms` | Button response 1 → 6 ms |
| `37_perf_debounce_6ms_to_3ms` | Button response 6 → 3 ms |
| `38_perf_ossens_6_to_7` | OS sensitivity 6 → 7 |
| `39_perf_ossens_7_to_6` | OS sensitivity 7 → 6 |
| `3a_perf_dblclick_7_to_8` | OS double-click 7 → 8 |
| `3b_perf_dblclick_8_to_7` | OS double-click 8 → 7 |
| `40_dpi_stage4_x_1600_to_1650_linked` | Typed 1650 into stage 4 X; MasterPlus wrote 1650 then reverted to 1600 |
| `50_light_breath_color_ff8000_to_red` | Breathing colour → FF0000 |
| `51_light_breath_color_red_to_blue` | Breathing colour → 0000FF |
| `52_light_breath_brightness_max_to_half` | Brightness max → ~half |
| `53_light_breath_brightness_half_to_max` | Brightness → max |
| `54_light_breath_speed_1_to_2` | LED speed tick 1 → 2 |
| `55_light_breath_speed_2_to_5` | LED speed tick 2 → 5 (encoded as 2?) |
| `56_light_breath_speed_5_to_1` | LED speed → tick 1 |
| `57_light_mode_breath_to_static` | Mode breathing → static |
| `58_light_mode_static_to_cycle` | Mode static → colour cycle |
| `59_light_mode_cycle_to_off` | Mode colour cycle → off |
| `5a_light_mode_off_to_breath` | Mode off → breathing |
| `5b_light_breath_speed_1_to_3` | LED speed tick 1 → 3 |
| `5c_light_breath_speed_3_to_4` | LED speed tick 3 → 4 |
| `5d_light_breath_speed_4_to_1` | LED speed tick 4 → 1 |
| `5e_light_breath_color_blue_to_red` | Colour → FF0000 (preset) |
| `5f_light_breath_color_typed_g_0_to_128` | Typed G=128 → FF8000 |
| `5g_light_breath_speed_1_to_5_retry` | LED speed → fastest tick (again `02`) |
| `5h_light_breath_speed_5_to_1` | LED speed → tick 1 |
| `60_buttons_click_mouse_combo_view` | Toggled the Combo-layer view (rewrites button block unchanged) |
| `61_btn_back_to_wheelclick` | Back button → wheel click |
| `62_btn_back_wheelclick_to_leftclick` | Back button → left click |
| `63_btn_back_to_browserback` | Back button → browser backward |
| `64_btn_back_to_disable` | Back button → disabled |
| `65_btn_back_disable_to_browserback` | Back button → browser backward |
| `66_btn_back_to_key_a` | Back button → keyboard "A" (stored as macro slot 3) |
| `67_btn_back_key_a_to_browserback` | Back button → browser backward |
| `70_btn_back_dpi_level2` | Back button → DPI level 2 |
| `71_btn_back_dpi_level4` | Back button → DPI level 4 |
| `72_btn_back_dpi_up` | Back button → DPI + |
| `73_btn_back_dpi_down` | Back button → DPI - |
| `74_btn_back_dpi_cycle_up` | Back button → DPI cycle + |
| `75_btn_back_dpi_cycle_down` | Back button → DPI cycle - |
| `76_btn_back_profile1` .. `7a_btn_back_profile5` | Back button → profile 1..5 |
| `7b_btn_back_profile_cycle_up` | Back button → profile cycle + |
| `7c_btn_back_profile_cycle_down` | Back button → profile cycle - |
| `7d_btn_back_to_browserback` | Back button → browser backward |
| `80_btn_back_mm_webbrowser` | Back button → web browser |
| `81_btn_back_mm_email` | Back button → e-mail |
| `82_btn_back_mm_calculator` | Back button → calculator |
| `83_btn_back_mm_mediaplayer` | Back button → media player |
| `84_btn_back_mm_playpause` | Back button → play/pause |
| `85_btn_back_mm_stop` | Back button → stop |
| `86_btn_back_mm_next` | Back button → next track |
| `87_btn_back_mm_prev` | Back button → previous track |
| `88_btn_back_sensor_onoff` | Back button → sensor on/off |
| `89_btn_back_to_browserback` | Back button → browser backward |
| `8a_btn_back_rapidfire_left_x3` | Back button → rapid fire left click × 3 (macro slot 3) |
| `8b_btn_back_rf_to_browserback` | Back button → browser backward |
| `90_combo_disable` | Mouse Combo disabled |
| `91_combo_enable` | Mouse Combo enabled |
| `92_btn_bottom_to_disable` | Bottom button → disabled |
| `93_btn_bottom_to_dpi_cycle_up` | Bottom button → DPI cycle + |
| `94_combo_right_to_playpause` | Combo-layer right button → play/pause |
| `95_combo_right_to_disable` | Combo-layer right button → disabled |
| `96_combo_right_to_ctrl_shift_a_b` | Combo-layer right button → Ctrl+Shift+A+B (macro slot 9) |
| `97_combo_right_kb_to_disable` | Combo-layer right button → disabled |
| `a0_btn_back_to_macro_t1_runonce` | Recorded macro T1 (X, Y with uneven delays) → back button, run once |
| `a1_macro_t1_holdloop` | T1 play mode → hold loop (rewrites slot 3) |
| `a2_macro_t1_toggleloop` | T1 play mode → toggle loop |
| `a3_macro_t1_runonce` | T1 play mode → run once |
| `a4_btn_back_macro_to_browserback` | Back button → browser backward |
| `a5_macro_t1_delete` | Deleted T1 in the Macros tab (no device traffic) |

### Wired (USB cable, `2516:0169`, root hub USBPcap1 device 8)

| File | Action |
|---|---|
| `b0_wired_masterplus_startup` | MasterPlus launched with the mouse on the cable (dongle still plugged in) |
| `b1_wired_polling_1000_to_500` | Polling 1000 → 500 Hz |
| `b2_wired_polling_500_to_1000` | Polling 500 → 1000 Hz |
| `b3_wired_btn_back_to_key_a` | Back button → keyboard "A" (macro slot 3, 11 pages) |
| `b4_wired_btn_back_to_browserback` | Back button → browser backward |

### Dongle while charging (cable to a power source; only the dongle enumerates)

| File | Action |
|---|---|
| `c0_dongle_charging_masterplus_startup` | MasterPlus launched; status reports show battery %, charging = 1, wireless = 1 |

### Re-enumeration (HID report descriptors)

| File | Action |
|---|---|
| `d0_dongle_replug_descriptors` | Dongle unplugged and replugged with capture on its hub (MasterPlus closed); contains all 5 HID report descriptors |
| `d1_cable_replug_descriptors` | Cable plugged in with capture on hub 1. Filtered to the mouse only (device address 10); the unfiltered hub capture was deleted because it covered other devices |

Final state after both sessions matches the starting state (profile 0: breathing
FF8000 full brightness speed 0, 1000 Hz, stages 2+4 enabled with 4 active,
3 ms debounce, 5 min sleep, 15 % low power, default button map, Combo
enabled). Exceptions: macro slots 3 and 9 hold unreferenced data from these
tests.
