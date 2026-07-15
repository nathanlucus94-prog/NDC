import tkinter as tk
from tkinter import ttk
import datetime
import math

def f_to_c(f):
    return (f - 32.0) * 5.0 / 9.0

def c_to_f(c):
    return (c * 9.0 / 5.0) + 32.0

def mph_to_kt(mph):
    return mph / 1.15078

def kt_to_mph(kt):
    return kt * 1.15078

def calculate_saturation_vapor_pressure(temp_c):
    """Tetens formula for saturation vapor pressure over water (hPa/mb)."""
    return 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))

def calculate_rh(temp_c, dew_point_c):
    try:
        es = calculate_saturation_vapor_pressure(temp_c)
        e = calculate_saturation_vapor_pressure(dew_point_c)
        return min(100.0, max(0.0, round((e / es) * 100, 1)))
    except:
        return None

def get_moist_adiabatic_lapse_rate(t_c, p_mb):
    """Calculates the exact pseudo-adiabatic lapse rate (C/m)."""
    t_k = t_c + 273.15
    es = calculate_saturation_vapor_pressure(t_c)
    w_s = 0.622 * es / (p_mb - es)
    
    g = 9.80665
    c_p = 1005.0
    l_v = 2.501e6
    r_d = 287.05
    r_v = 461.5
    
    numerator = g * (1.0 + (l_v * w_s) / (r_d * t_k))
    denominator = c_p + (l_v**2 * w_s * 0.622) / (r_v * t_k**2)
    
    return numerator / denominator

def interpolate_wind_vector(p, s_press, s_w_kt, s_d, w_500_kt, d_500):
    if None in [s_w_kt, s_d, w_500_kt, d_500]:
        return None, None
    
    pct = (s_press - p) / (s_press - 500.0) if s_press > 500.0 else 1.0
    pct = max(0.0, min(1.0, pct))
    w_speed = s_w_kt + pct * (w_500_kt - s_w_kt)
    
    r_s_d = math.radians(s_d)
    r_d_500 = math.radians(d_500)
    u_s = s_w_kt * math.sin(r_s_d)
    v_s = s_w_kt * math.cos(r_s_d)
    u_500 = w_500_kt * math.sin(r_d_500)
    v_500 = w_500_kt * math.cos(r_d_500)
    
    u_interp = u_s + pct * (w_500_kt * math.sin(r_d_500) - u_s)
    v_interp = v_s + pct * (w_500_kt * math.cos(r_d_500) - v_s)
    
    w_dir = math.degrees(math.atan2(u_interp, v_interp))
    if w_dir < 0:
        w_dir += 360.0
        
    return w_speed, round(w_dir, 1)

def run_atmospheric_sounding(inputs, hours_ahead):
    s_temp_f = inputs.get("temp")
    s_dew_f = inputs.get("dew")
    s_rh_manual = inputs.get("rh_manual")
    s_press = inputs.get("press") if inputs.get("press") is not None else 1013.2
    
    s_wind_mph = inputs.get("wind")
    s_wind_dir = inputs.get("wind_dir")
    s_wind_500_mph = inputs.get("wind_500")
    s_wind_dir_500 = inputs.get("wind_dir_500")
    mid_lapse = inputs.get("mid_lapse") if inputs.get("mid_lapse") is not None else 6.5
    
    elevation = inputs.get("elevation") if inputs.get("elevation") is not None else 0.0
    cloud_cover = inputs.get("cloud_cover") if inputs.get("cloud_cover") is not None else 0.0
    rainfall = inputs.get("rainfall") if inputs.get("rainfall") is not None else 0.0

    if s_temp_f is None:
        return None, 0.0

    s_temp = f_to_c(s_temp_f)
    
    if s_dew_f == "" or s_dew_f is None:
        if s_rh_manual is not None and s_rh_manual > 0:
            try:
                rh_fraction = s_rh_manual / 100.0
                es = calculate_saturation_vapor_pressure(s_temp)
                e = es * rh_fraction
                s_dew = (243.5 * math.log(e / 6.112)) / (17.67 - math.log(e / 6.112))
            except:
                s_dew = None
        else:
            s_dew = None
    else:
        s_dew = f_to_c(s_dew_f)

    if s_dew is None:
        return None, 0.0
    
    if s_dew > s_temp: 
        s_dew = s_temp

    s_wind_kt = mph_to_kt(s_wind_mph) if s_wind_mph is not None else None
    s_wind_500_kt = mph_to_kt(s_wind_500_mph) if s_wind_500_mph is not None else None
    cloud_cover = max(0.0, min(1.0, cloud_cover))

    soil_moisture_factor = min(1.0, rainfall / 25.0)
    solar_insolation_modifier = 1.0 - (cloud_cover * 0.6)
    
    temp_trend_rate = 0.45 * solar_insolation_modifier * (1.0 - (soil_moisture_factor * 0.4))
    dew_trend_rate = 0.12 * (1.0 + (soil_moisture_factor * 0.5)) * solar_insolation_modifier

    target_s_temp = s_temp - (hours_ahead * temp_trend_rate)
    target_s_dew = s_dew - (hours_ahead * dew_trend_rate)
    
    p = s_press
    dp = 2.0  
    h = elevation
    env_profile = []
    
    while p >= 500.0:
        if p >= 900.0:
            pct = (s_press - p) / (s_press - 900.0) if s_press > 900.0 else 1.0
            t_env = target_s_temp - (7.5 * pct)
        elif p >= 750.0:
            pct = (900.0 - p) / 150.0
            t_env = (target_s_temp - 7.5) - (9.0 * pct)
        else:
            h_delta_km = (750.0 - p) * 0.012  
            t_env = (target_s_temp - 16.5) - (mid_lapse * h_delta_km)

        h_lcl_agl = max(0.0, (target_s_temp - target_s_dew) * 125.0)
        h_lcl_msl = elevation + h_lcl_agl

        if h <= h_lcl_msl:
            h_agl = h - elevation
            pct = h_agl / h_lcl_agl if h_lcl_agl > 0 else 1.0
            t_d_env = target_s_dew - (2.0 * pct)
        else:
            h_above_lcl_km = (h - h_lcl_msl) / 1000.0
            t_d_env = (target_s_dew - 2.0) - (6.0 * h_above_lcl_km)
        t_d_env = max(-70.0, t_d_env)

        t_env_k = t_env + 273.15
        dh = (287.05 * t_env_k / 9.80665) * (dp / p)
        
        w_spd_kt, w_dir = interpolate_wind_vector(p, s_press, s_wind_kt, s_wind_dir, s_wind_500_kt, s_wind_dir_500)
        w_spd_mph = kt_to_mph(w_spd_kt) if w_spd_kt is not None else None

        env_profile.append({
            'p': p,
            'h': h,
            't_env': t_env,
            't_d_env': t_d_env,
            'w_spd_mph': w_spd_mph,
            'w_dir': w_dir,
            'dh': dh
        })
        h += dh
        p -= dp

    best_cape = -1.0
    best_cin = 0.0
    best_parcel_track = []
    best_lfc_p = None
    best_lcl_p = None
    best_cap_p = None
    
    source_pressures = []
    curr_sp = s_press
    while curr_sp >= 700.0:
        source_pressures.append(curr_sp)
        curr_sp -= 50.0

    for source_p in source_pressures:
        closest_env = min(env_profile, key=lambda x: abs(x['p'] - source_p))
        tp_start = closest_env['t_env']
        dp_start = closest_env['t_d_env']
        
        p_lcl = source_p - ((tp_start - dp_start) * 4.4) 
        
        p_idx = 0
        current_cape = 0.0
        current_cin = 0.0
        track = []
        t_parcel = tp_start
        
        lfc_found = False
        local_lfc_p = None
        local_lcl_p = None
        local_cap_p = None
        max_negative_buoyancy = 0.0

        for layer in env_profile:
            if layer['p'] > source_p:
                continue
            
            if p_idx == 0:
                t_parcel = tp_start
            else:
                if layer['p'] >= p_lcl:
                    t_parcel -= 0.0098 * layer['dh']
                else:
                    gamma_m = get_moist_adiabatic_lapse_rate(t_parcel, layer['p'])
                    t_parcel -= gamma_m * layer['dh']
            
            if abs(layer['p'] - p_lcl) <= 4.0 and local_lcl_p is None:
                local_lcl_p = layer['p']

            dt = t_parcel - layer['t_env']
            t_env_k = layer['t_env'] + 273.15
            
            if layer['p'] <= p_lcl:
                if dt > 0:
                    current_cape += 9.80665 * (dt / t_env_k) * layer['dh']
                    if not lfc_found:
                        lfc_found = True
                        local_lfc_p = layer['p']
                else:
                    if layer['p'] > 700.0:
                        current_cin += 9.80665 * (dt / t_env_k) * layer['dh']
                        if dt < max_negative_buoyancy:
                            max_negative_buoyancy = dt
                            local_cap_p = layer['p']

            track.append({'p': layer['p'], 't_p_f': c_to_f(t_parcel)})
            p_idx += 1

        if current_cape > best_cape:
            best_cape = current_cape
            best_cin = current_cin
            best_parcel_track = track
            best_lfc_p = local_lfc_p
            best_lcl_p = local_lcl_p
            best_cap_p = local_cap_p if best_cin < -20 else None

    plot_points = []
    level_readouts = {}
    target_pressures = {"Surface": s_press, "900mb": 900.0, "750mb": 750.0, "500mb": 500.0}

    for layer in env_profile:
        p_val = layer['p']
        t_p_f_val = c_to_f(layer['t_env'])
        for track_node in best_parcel_track:
            if abs(track_node['p'] - p_val) < 0.1:
                t_p_f_val = track_node['t_p_f']
                break
                
        plot_points.append({
            'p': p_val,
            'h_km': layer['h'] / 1000.0,
            't_env_f': c_to_f(layer['t_env']),
            't_d_f': c_to_f(layer['t_d_env']),
            't_p_f': t_p_f_val,
            'w_spd_mph': layer['w_spd_mph'],
            'w_dir': layer['w_dir']
        })

        for lvl_name, target_p in target_pressures.items():
            if abs(p_val - target_p) <= 1.0:
                level_readouts[lvl_name] = {
                    "temp_f": round(c_to_f(layer['t_env']), 1),
                    "dew_f": round(c_to_f(layer['t_d_env']), 1),
                    "rh": calculate_rh(layer['t_env'], layer['t_d_env']),
                    "wind_mph": round(layer['w_spd_mph'], 1) if layer['w_spd_mph'] is not None else None,
                    "wind_dir": layer['w_dir']
                }

    lapse_rates_report = ""
    for check_p in [950, 850, 750, 650]:
        p_top = check_p - 25
        p_bot = check_p + 25
        node_top = min(env_profile, key=lambda x: abs(x['p'] - p_top))
        node_bot = min(env_profile, key=lambda x: abs(x['p'] - p_bot))
        dz_km = (node_top['h'] - node_bot['h']) / 1000.0
        if dz_km > 0:
            lr = (node_bot['t_env'] - node_top['t_env']) / dz_km
            lapse_rates_report += f"Lapse {int(p_bot)}-{int(p_top)}mb: {round(lr,1)} °C/km\n"

    bulk_shear_mph = round(s_wind_500_mph - s_wind_mph, 1) if (s_wind_mph is not None and s_wind_500_mph is not None) else None
    provided_count = sum(1 for f in ["temp", "dew", "press", "wind", "wind_500"] if inputs.get(f) is not None)
    accuracy = 95.0 - (10 - provided_count) * 4.0 - (hours_ahead * 1.2)

    diagnostics = {
        "cape": max(0, int(best_cape)),
        "cin": min(0, int(best_cin)),
        "shear_mph": bulk_shear_mph,
        "lcl_p": best_lcl_p,
        "lfc_p": best_lfc_p,
        "cap_p": best_cap_p,
        "lr_text": lapse_rates_report
    }

    return {"profile": plot_points, "levels": level_readouts, "diagnostics": diagnostics}, max(5.0, round(accuracy, 1))


class AdvancedSoundingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enforced Severe Weather Sounding Thermodynamic Engine (Convective Diagnostics)")
        self.root.geometry("1160x900")
        self.root.resizable(False, False)
        ttk.Style().theme_use("clam")
        
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.drag_start_x = 0.0
        self.drag_start_y = 0.0

        self.create_layout()
        self.load_severe_preset()
        self.attach_mouse_bindings()

    def create_layout(self):
        # Increased panel width slightly to comfortably fit text side-by-side
        left_panel = ttk.Frame(self.root, padding=10, width=440)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        right_panel = ttk.Frame(self.root, padding=15)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(left_panel, text="Sounding Configuration", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 2))
        
        # Grid frame container to compress vertical spacing 
        grid_frame = ttk.Frame(left_panel)
        grid_frame.pack(fill=tk.X, pady=0)

        self.entries = {}
        input_fields = [
            ("Surface Temp (°F)", "temp"),
            ("Surface Dew Pt (°F)", "dew"),
            ("Surface Manual RH (%)", "rh_manual"),
            ("Surface Press (mb)", "press"),
            ("Surface Wind (mph)", "wind"),
            ("Sfc Wind Dir (0-360)", "wind_dir"),
            ("500mb Wind (mph)", "wind_500"),
            ("500mb Wind Dir", "wind_dir_500"),
            ("Mid Lapse (°C/km)", "mid_lapse"),
            ("Elevation (meters)", "elevation"),
            ("Cloud Cover (0-1)", "cloud_cover"),
            ("24h Rain (mm)", "rainfall")
        ]

        # Render input elements in compact 2-column grid layout
        for idx, (label, key) in enumerate(input_fields):
            r = idx // 2
            c = (idx % 2) * 2
            lbl = ttk.Label(grid_frame, text=label, font=("Arial", 8, "bold"))
            lbl.grid(row=r, column=c, sticky=tk.W, padx=(5, 2), pady=1)
            ent = ttk.Entry(grid_frame, width=12)
            ent.grid(row=r, column=c+1, sticky=tk.EW, padx=(0, 5), pady=1)
            ent.bind("<KeyRelease>", lambda e: self.recalculate())
            self.entries[key] = ent

        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="Load Severe Preset", command=self.load_severe_preset).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_frame, text="Reset View", command=self.reset_view).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_frame, text="Clear", command=self.clear_fields).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # --- NEW AD HOC LAPSE RATE CALCULATOR UI SECTION ---
        calc_border = ttk.LabelFrame(left_panel, text=" Quick Lapse Rate Calculator ", padding=8)
        calc_border.pack(fill=tk.X, pady=4)
        
        ttk.Label(calc_border, text="Bottom Prs (mb):", font=("Arial", 8)).grid(row=0, column=0, sticky=tk.W)
        self.lr_p_bot = ttk.Entry(calc_border, width=8)
        self.lr_p_bot.grid(row=0, column=1, pady=1, padx=2)
        self.lr_p_bot.insert(0, "1000")
        
        ttk.Label(calc_border, text="Bottom Temp (°F):", font=("Arial", 8)).grid(row=0, column=2, sticky=tk.W)
        self.lr_t_bot = ttk.Entry(calc_border, width=8)
        self.lr_t_bot.grid(row=0, column=3, pady=1, padx=2)
        self.lr_t_bot.insert(0, "85")

        ttk.Label(calc_border, text="Top Prs (mb):", font=("Arial", 8)).grid(row=1, column=0, sticky=tk.W)
        self.lr_p_top = ttk.Entry(calc_border, width=8)
        self.lr_p_top.grid(row=1, column=1, pady=1, padx=2)
        self.lr_p_top.insert(0, "700")

        ttk.Label(calc_border, text="Top Temp (°F):", font=("Arial", 8)).grid(row=1, column=2, sticky=tk.W)
        self.lr_t_top = ttk.Entry(calc_border, width=8)
        self.lr_t_top.grid(row=1, column=3, pady=1, padx=2)
        self.lr_t_top.insert(0, "46")
        
        self.lr_result_lbl = ttk.Label(calc_border, text="Calculated Rate: -- °C/km", font=("Arial", 9, "bold"), foreground="#00FF00")
        self.lr_result_lbl.grid(row=2, column=0, columnspan=4, pady=(4, 0))
        
        # Bind key listeners to fire manual calculations inside tool frame
        self.lr_p_bot.bind("<KeyRelease>", lambda e: self.run_quick_lapse_calc())
        self.lr_t_bot.bind("<KeyRelease>", lambda e: self.run_quick_lapse_calc())
        self.lr_p_top.bind("<KeyRelease>", lambda e: self.run_quick_lapse_calc())
        self.lr_t_top.bind("<KeyRelease>", lambda e: self.run_quick_lapse_calc())

        ttk.Label(left_panel, text="Calculated Thermodynamics", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(4, 2))
        self.diag_box = tk.Text(left_panel, height=14, bg="#111", fg="#00FF00", font=("Consolas", 9), padx=5, pady=5)
        self.diag_box.pack(fill=tk.X)
        self.diag_box.config(state=tk.DISABLED)

        top_bar = ttk.Frame(right_panel)
        top_bar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(top_bar, text="Forecast Profile Step:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.slider = tk.Scale(top_bar, from_=0, to=24, orient=tk.HORIZONTAL, length=240, tickinterval=4, command=lambda e: self.recalculate())
        self.slider.pack(side=tk.LEFT, padx=10)
        
        self.acc_lbl = ttk.Label(top_bar, text="Accuracy: --", font=("Arial", 12, "bold"))
        self.acc_lbl.pack(side=tk.RIGHT, padx=10)

        self.time_lbl = ttk.Label(right_panel, text="Valid Time:", font=("Arial", 9, "italic"))
        self.time_lbl.pack(anchor=tk.W, pady=(0, 5))

        self.canvas = tk.Canvas(right_panel, width=660, height=640, bg="#151515", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def run_quick_lapse_calc(self):
        """Helper method to parse ad-hoc input pairs and compute exact environmental lapse rates."""
        try:
            p_b = float(self.lr_p_bot.get().strip())
            t_b_f = float(self.lr_t_bot.get().strip())
            p_t = float(self.lr_p_top.get().strip())
            t_t_f = float(self.lr_t_top.get().strip())
            
            if p_b <= p_t or p_t <= 0:
                self.lr_result_lbl.config(text="Error: Bottom pressure must be > Top", foreground="red")
                return
                
            # Convert standard heights using international barometric formulas
            h_b = 44330.8 * (1.0 - (p_b / 1013.25)**(1.0 / 5.25588))
            h_t = 44330.8 * (1.0 - (p_t / 1013.25)**(1.0 / 5.25588))
            dz_km = (h_t - h_b) / 1000.0
            
            if dz_km <= 0:
                self.lr_result_lbl.config(text="Error: Invalid layer thickness", foreground="red")
                return
                
            dt_c = f_to_c(t_b_f) - f_to_c(t_t_f)
            lapse_val = dt_c / dz_km
            self.lr_result_lbl.config(text=f"Calculated Rate: {round(lapse_val, 2)} °C/km", foreground="#00FF00")
        except ValueError:
            self.lr_result_lbl.config(text="Error: Non-numeric values entered", foreground="orange")

    def attach_mouse_bindings(self):
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_move)
        self.canvas.bind("<MouseWheel>", self.on_mouse_zoom)
        self.canvas.bind("<Button-4>", self.on_mouse_zoom)
        self.canvas.bind("<Button-5>", self.on_mouse_zoom)

    def on_drag_start(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag_move(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.pan_offset_x += dx
        self.pan_offset_y += dy
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.recalculate()

    def on_mouse_zoom(self, event):
        mx, my = event.x, event.y
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        else:
            factor = 0.85
            
        new_zoom = max(0.4, min(12.0, self.zoom_factor * factor))
        self.pan_offset_x = mx - (mx - self.pan_offset_x) * (new_zoom / self.zoom_factor)
        self.pan_offset_y = my - (my - self.pan_offset_y) * (new_zoom / self.zoom_factor)
        self.zoom_factor = new_zoom
        self.recalculate()

    def reset_view(self):
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.recalculate()

    def transform_x(self, raw_x):
        return (raw_x * self.zoom_factor) + self.pan_offset_x

    def transform_y(self, raw_y):
        return (raw_y * self.zoom_factor) + self.pan_offset_y

    def temp_to_x(self, temp_f):
        base_x = 50 + ((temp_f + 60) / 200.0) * 400
        return self.transform_x(base_x)

    def press_to_y(self, p, s_press):
        base_y = 570 - (math.log(s_press / p) / math.log(s_press / 500.0)) * 520
        return self.transform_y(base_y)

    def get_parsed_inputs(self):
        data = {}
        for k, entry in self.entries.items():
            txt = entry.get().strip()
            try:
                data[k] = float(txt)
            except ValueError:
                data[k] = None
        return data

    def draw_wind_barb(self, cx, cy, speed_mph, direction):
        if speed_mph is None or speed_mph < 1:
            self.canvas.create_oval(cx-4, cy-4, cx+4, cy+4, outline="#00FF00", width=1)
            return

        rad = math.radians(direction)
        dx = math.sin(rad)
        dy = -math.cos(rad)

        barb_len = 30 * self.zoom_factor
        end_x = cx + dx * barb_len
        end_y = cy + dy * barb_len
        self.canvas.create_line(cx, cy, end_x, end_y, fill="#00FF00", width=max(1, 1.5 * self.zoom_factor))

        curr_speed = mph_to_kt(speed_mph)
        feather_loc = 1.0
        
        perp_rad = rad - math.pi / 2
        pdx = math.sin(perp_rad)
        pdy = -math.cos(perp_rad)

        while curr_speed >= 48:
            fx = cx + dx * (barb_len * feather_loc)
            fy = cy + dy * (barb_len * feather_loc)
            fx_next = cx + dx * (barb_len * (feather_loc - 0.15))
            fy_next = cy + dy * (barb_len * (feather_loc - 0.15))
            tip_x = fx + pdx * (10 * self.zoom_factor)
            tip_y = fy + pdy * (10 * self.zoom_factor)
            
            self.canvas.create_polygon(fx, fy, tip_x, tip_y, fx_next, fy_next, fill="#00FF00", outline="#00FF00")
            feather_loc -= 0.18
            curr_speed -= 50

        while curr_speed >= 8:
            fx = cx + dx * (barb_len * feather_loc)
            fy = cy + dy * (barb_len * feather_loc)
            tip_x = fx + pdx * (10 * self.zoom_factor)
            tip_y = fy + pdy * (10 * self.zoom_factor)
            self.canvas.create_line(fx, fy, tip_x, tip_y, fill="#00FF00", width=max(1, 1.5 * self.zoom_factor))
            feather_loc -= 0.12
            curr_speed -= 10

        if curr_speed >= 3:
            fx = cx + dx * (barb_len * feather_loc)
            fy = cy + dy * (barb_len * feather_loc)
            tip_x = fx + pdx * (5 * self.zoom_factor)
            tip_y = fy + pdy * (5 * self.zoom_factor)
            self.canvas.create_line(fx, fy, tip_x, tip_y, fill="#00FF00", width=max(1, 1.5 * self.zoom_factor))

    def draw_skew_grid(self, s_press):
        self.canvas.delete("all")
        
        if self.zoom_factor >= 5.0:
            t_step = 2
        elif self.zoom_factor >= 2.8:
            t_step = 5
        elif self.zoom_factor >= 1.6:
            t_step = 10
        else:
            t_step = 20

        for t in range(-60, 141, t_step):
            x = self.temp_to_x(t)
            if t % 20 == 0:
                line_color = "#333333"
                text_color = "#999"
                font_weight = "bold"
            else:
                line_color = "#202020"
                text_color = "#555"
                font_weight = "normal"
                
            self.canvas.create_line(x, self.transform_y(40), x, self.transform_y(570), fill=line_color, dash=(2, 3))
            self.canvas.create_text(x, self.transform_y(585), text=f"{t}°F", fill=text_color, font=("Arial", max(8, min(10, int(8*self.zoom_factor))), font_weight))

        y_pressures = [s_press]
        p_step = 25 if self.zoom_factor >= 3.0 else (50 if self.zoom_factor >= 1.7 else 100)
        
        curr_p = 1000.0
        while curr_p >= 500.0:
            if curr_p < s_press:
                y_pressures.append(curr_p)
            curr_p -= p_step

        for p_lev in y_pressures:
            y = self.press_to_y(p_lev, s_press)
            is_major = (int(p_lev) % 100 == 0 or p_lev == s_press)
            
            l_color = "#444" if is_major else "#262626"
            t_color = "#fff" if is_major else "#888"
            
            self.canvas.create_line(self.transform_x(50), y, self.transform_x(450), y, fill=l_color, width=1)
            self.canvas.create_text(self.transform_x(42), y, text=f"{int(p_lev)}mb", fill=t_color, font=("Arial", max(8, min(10, int(9*self.zoom_factor))), "bold" if is_major else "normal"), anchor=tk.E)

    def draw_convective_zones(self, s_press, diags):
        lcl = diags.get("lcl_p")
        lfc = diags.get("lfc_p")
        cap = diags.get("cap_p")

        if lcl and lfc and (lcl > lfc):
            y_lcl = self.press_to_y(lcl, s_press)
            y_lfc = self.press_to_y(lfc, s_press)
            
            self.canvas.create_line(self.transform_x(50), y_lcl, self.transform_x(450), y_lcl, fill="#00FF00", width=2, dash=(4, 2))
            self.canvas.create_line(self.transform_x(50), y_lfc, self.transform_x(450), y_lfc, fill="#00FF00", width=2, dash=(4, 2))
            
            self.canvas.create_rectangle(self.transform_x(50), y_lfc, self.transform_x(450), y_lcl, fill="", outline="#00FF00", width=1, stipple="gray25")
            self.canvas.create_text(self.transform_x(440), (y_lcl + y_lfc)/2, text="STORM GENESIS ZONE", fill="#00FF00", font=("Arial", 8, "bold"), anchor=tk.E)

        if cap:
            y_cap = self.press_to_y(cap, s_press)
            self.canvas.create_line(self.transform_x(45), y_cap, self.transform_x(455), y_cap, fill="#FF0000", width=3)
            self.canvas.create_text(self.transform_x(55), y_cap - 8, text="CIN CAP INVERSION LAYER", fill="#FF3333", font=("Arial", 8, "bold"), anchor=tk.W)

    def recalculate(self):
        inputs = self.get_parsed_inputs()
        hour = self.slider.get()
        
        f_time = datetime.datetime.now() + datetime.timedelta(hours=hour)
        self.time_lbl.config(text=f"Verification Baseline: {f_time.strftime('%I:%M %p')} | Evolution Timeline: +{hour} Hr")

        s_press_val = inputs.get("press") if inputs.get("press") is not None else 1013.2
        self.draw_skew_grid(s_press_val)
        
        data, accuracy = run_atmospheric_sounding(inputs, hour)
        if data is None:
            self.acc_lbl.config(text="Accuracy: 0.0%", foreground="gray")
            return

        self.acc_lbl.config(text=f"Accuracy: {accuracy}%")
        self.acc_lbl.config(foreground="#00FF00" if accuracy > 70 else ("orange" if accuracy > 45 else "red"))

        diags = data["diagnostics"]
        self.draw_convective_zones(s_press_val, diags)

        display_y_levels = [s_press_val, 950.0, 900.0, 850.0, 800.0, 750.0, 700.0, 650.0, 600.0, 550.0, 500.0]
        p_step_filter = 25 if self.zoom_factor >= 3.0 else (50 if self.zoom_factor >= 1.7 else 100)

        for p_target in display_y_levels:
            if p_target != s_press_val and int(p_target) % p_step_filter != 0:
                continue
            y = self.press_to_y(p_target, s_press_val)
            
            closest_pts = [x for x in data["profile"] if abs(x['p'] - p_target) < 1.5]
            if closest_pts:
                closest_pt = closest_pts[0]
                rh_val = calculate_rh(f_to_c(closest_pt['t_env_f']), f_to_c(closest_pt['t_d_f']))
                if rh_val is not None:
                    r_text = f"RH: {rh_val}%"
                    self.canvas.create_text(self.transform_x(458), y, text=r_text, fill="#aaa", font=("Consolas", 9), anchor=tk.W)

        p_data = data["profile"]
        for i in range(len(p_data) - 1):
            pt1 = p_data[i]
            pt2 = p_data[i+1]
            y1, y2 = self.press_to_y(pt1['p'], s_press_val), self.press_to_y(pt2['p'], s_press_val)

            self.canvas.create_line(self.temp_to_x(pt1['t_env_f']), y1, self.temp_to_x(pt2['t_env_f']), y2, fill="red", width=max(1, int(2*self.zoom_factor)))
            self.canvas.create_line(self.temp_to_x(pt1['t_d_f']), y1, self.temp_to_x(pt2['t_d_f']), y2, fill="cyan", width=max(1, int(2*self.zoom_factor)))
            self.canvas.create_line(self.temp_to_x(pt1['t_p_f']), y1, self.temp_to_x(pt2['t_p_f']), y2, fill="#ffaa00", width=max(1, int(2*self.zoom_factor)), dash=(2, 2))

        if p_data:
            target_p_barb = s_press_val
            barb_interval = 37.5 if self.zoom_factor >= 2.5 else 75.0
            while target_p_barb >= 500.0:
                closest_pt = min(p_data, key=lambda x: abs(x['p'] - target_p_barb))
                if closest_pt['w_spd_mph'] is not None:
                    by = self.press_to_y(closest_pt['p'], s_press_val)
                    bx = self.transform_x(550)
                    self.draw_wind_barb(bx, by, closest_pt['w_spd_mph'], closest_pt['w_dir'])
                    
                    label_str = f"{int(closest_pt['w_spd_mph'])}mph {int(closest_pt['w_dir'])}°"
                    self.canvas.create_text(bx + (45 * self.zoom_factor), by, text=label_str, fill="#888", font=("Consolas", 9), anchor=tk.W)
                target_p_barb -= barb_interval

        self.canvas.create_rectangle(self.transform_x(50), self.transform_y(40), self.transform_x(450), self.transform_y(570), outline="#555")

        legends = [("red", "Env Temp (°F)", 40), ("cyan", "Env Dew Pt (°F)", 60), ("#ffaa00", "Max MUCAPE Track", 80)]
        for col, txt, y_offset in legends:
            self.canvas.create_line(490, y_offset, 520, y_offset, fill=col, width=2, dash=(3,3) if "MUCAPE" in txt else None)
            self.canvas.create_text(530, y_offset, text=txt, fill="#ddd", anchor=tk.W, font=("Arial", 9))
            
        self.canvas.create_text(self.transform_x(550), self.transform_y(25), text="Wind Profile", fill="#fff", font=("Arial", 10, "bold"))

        # FIX: Swapped out nested f-strings with cleanly escaped double quotes to resolve execution syntax issues
        self.diag_box.config(state=tk.NORMAL)
        self.diag_box.delete("1.0", tk.END)
        
        report = (
            f"=== THERMO METRICS ===\n"
            f"MUCAPE : {diags['cape']} J/kg\n"
            f"CIN    : {diags['cin']} J/kg\n"
            f"LCL Prs: {(str(int(diags['lcl_p'])) + ' mb') if diags['lcl_p'] else 'None'}\n"
            f"LFC Prs: {(str(int(diags['lfc_p'])) + ' mb') if diags['lfc_p'] else 'CIN Capped'}\n\n"
            f"=== 50MB INTERVAL LAPSE RATES ===\n"
            f"{diags['lr_text']}\n"
            f"=== KINEMATICS ===\n"
            f"0-6km Bulk Shear:\n"
            f" --> {diags['shear_mph'] if diags['shear_mph'] is not None else '--'} mph\n"
        )
        self.diag_box.insert(tk.END, report)
        self.diag_box.config(state=tk.DISABLED)
        
        # Trigger an updated standalone quick-calculation sequence 
        self.run_quick_lapse_calc()

    def load_severe_preset(self):
        presets = {
            "temp": "93.2",        
            "dew": "77.0",         
            "rh_manual": "", 
            "press": "1006.0", 
            "wind": "17.3",        
            "wind_dir": "160",  
            "wind_500": "74.8",    
            "wind_dir_500": "270",  
            "mid_lapse": "8.2",
            "elevation": "150",
            "cloud_cover": "0.2",
            "rainfall": "0.0"
        }
        for k, v in self.entries.items():
            v.delete(0, tk.END)
            v.insert(0, presets[k])
        self.recalculate()

    def clear_fields(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        self.recalculate()

if __name__ == "__main__":
    root = tk.Tk()
    app = AdvancedSoundingApp(root)
    root.mainloop()