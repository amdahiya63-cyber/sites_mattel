
import os
import sqlite3
import pandas as pd
import streamlit as st
import streamlit as st

# --- Utilisateurs autorisés ---
USERS = {
    "admin": "motdepassefort",   # Toi = accès complet
    "guest": "visiteur123"       # Collègues = lecture seule
}

# --- Formulaire de connexion ---
st.sidebar.title("🔑 Connexion")
username = st.sidebar.text_input("Utilisateur")
password = st.sidebar.text_input("Mot de passe", type="password")

if username in USERS and USERS[username] == password:
    st.sidebar.success(f"Bienvenue {username} 👋")

    # Définir les droits
    if username == "admin":
        st.sidebar.info("⚡ Accès ADMIN (lecture + écriture)")
        is_admin = True
    else:
        st.sidebar.info("👀 Accès VISITEUR (lecture seule)")
        is_admin = False
else:
    st.error("⛔ Identifiants incorrects")
    st.stop()
DB_PATH = os.path.join(os.path.dirname(__file__), "sites_mattel.db")
MEDIA_DIR = os.path.join(os.path.dirname(__file__), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

st.set_page_config(page_title="SITES MATTEL", layout="wide")

@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def df(query, params=()):
    return pd.read_sql_query(query, get_conn(), params=params)

def exec_sql(query, params=()):
    c = get_conn().cursor()
    c.execute(query, params)
    get_conn().commit()
    return c.lastrowid

st.sidebar.title("SITES MATTEL")
page = st.sidebar.radio("Navigation", ["Dashboard","Sites","FO Links","FH Links","Énergie","Datacom","VSAT","Photos"])

if page=="Dashboard":
    st.title("📊 Dashboard")
    sites = df("""
        SELECT s.site_id, s.site_code, s.site_name, c.name AS center, COALESCE(z.name,'') AS zone,
               s.latitude, s.longitude, s.is_active
        FROM site s
        JOIN center c ON s.center_id=c.center_id
        LEFT JOIN zone z ON s.zone_id=z.zone_id
    """)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Sites actifs", int((sites["is_active"]==1).sum()) if not sites.empty else 0)
    c2.metric("Total sites", 0 if sites is None else len(sites))
    c3.metric("Centres", int(df("SELECT COUNT(*) AS n FROM center")["n"].iloc[0]))
    c4.metric("Zones", int(df("SELECT COUNT(*) AS n FROM zone")["n"].iloc[0]))
    if not sites.empty:
        try:
            st.map(sites.rename(columns={"latitude":"lat","longitude":"lon"})[["lat","lon"]].dropna())
        except Exception as e:
            st.warning(e)
    st.dataframe(sites)

elif page=="Sites":
    st.title("🏗️ Sites – Créer / Modifier")
    centers = df("SELECT center_id, name || ' (' || COALESCE(code,'') || ')' AS label FROM center")
    zones = df("SELECT zone_id, name FROM zone")
    site_list = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    options = [None] + site_list["site_id"].tolist()
    def fmt_site(x):
        if x is None: return "— Nouveau —"
        return site_list.set_index("site_id").loc[x,"site_code"]
    selected = st.selectbox("Sélectionner un site", options, format_func=fmt_site)
    if selected is not None:
        row = df("SELECT * FROM site WHERE site_id=?", (selected,)).iloc[0].to_dict()
    else:
        row = {"site_id":None,"site_code":"","site_name":"","center_id":1,"zone_id":1,"latitude":0.0,"longitude":0.0,"altitude_m":0.0,"address":"","is_active":1,"commissioning_date":"","notes":""}
    with st.form("site_form"):
        c1,c2,c3 = st.columns(3)
        row["site_code"] = c1.text_input("Code site*", value=row.get("site_code") or "")
        row["site_name"] = c2.text_input("Nom site", value=row.get("site_name") or "")
        center_map = {r["label"]:r["center_id"] for _,r in centers.iterrows()}
        center_values = list(center_map.values())
        if row.get("center_id") in center_values:
            idx = center_values.index(row.get("center_id"))
        else:
            idx = 0
        row["center_id"] = c3.selectbox("Centre*", center_values, index=idx, format_func=lambda v: [k for k,val in center_map.items() if val==v][0])
        zids = [None] + zones["zone_id"].tolist()
        if row.get("zone_id") in zids: zidx = zids.index(row.get("zone_id"))
        else: zidx = 1 if len(zids)>1 else 0
        row["zone_id"] = st.selectbox("Zone", zids, index=zidx, format_func=lambda v: "" if v is None else zones.set_index("zone_id").loc[v,"name"])
        d1,d2,d3,d4 = st.columns(4)
        row["latitude"]  = d1.number_input("Latitude", value=float(row.get("latitude") or 0.0), format="%.6f")
        row["longitude"] = d2.number_input("Longitude", value=float(row.get("longitude") or 0.0), format="%.6f")
        row["altitude_m"]= d3.number_input("Altitude (m)", value=float(row.get("altitude_m") or 0.0))
        row["is_active"] = d4.selectbox("Actif ?", [0,1], index=int(row.get("is_active")==1))
        row["commissioning_date"] = st.text_input("Date mise en service (YYYY-MM-DD)", value=row.get("commissioning_date") or "")
        row["address"] = st.text_input("Adresse", value=row.get("address") or "")
        row["notes"] = st.text_area("Notes", value=row.get("notes") or "")
        if st.form_submit_button("💾 Enregistrer"):
            cols = list(row.keys())
            placeholders = ",".join(["?"]*len(cols))
            if row.get("site_id"):
                set_clause = ",".join([f"{c}=?" for c in cols if c!="site_id"])
                params = [row[c] for c in cols if c!="site_id"] + [row["site_id"]]
                exec_sql(f"UPDATE site SET {set_clause} WHERE site_id=?", params)
                st.success(f"Mise à jour: {row['site_code']}")
            else:
                exec_sql(f"INSERT INTO site({','.join([c for c in cols if c!='site_id'])}) VALUES ({','.join(['?']*(len(cols)-1))})", [row[c] for c in cols if c!="site_id"])
                st.success("Créé.")
    st.subheader("Liste")
    st.dataframe(df("SELECT s.site_code, s.site_name, c.name AS center, COALESCE(z.name,'') AS zone, s.latitude, s.longitude, s.is_active FROM site s JOIN center c ON s.center_id=c.center_id LEFT JOIN zone z ON s.zone_id=z.zone_id ORDER BY s.site_code"))

elif page=="FO Links":
    st.title("🧵 FO Links")
    sites = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    site_map = {r["site_code"]:r["site_id"] for _,r in sites.iterrows()}
    with st.form("fo_form"):
        a = st.selectbox("Site A", list(site_map.keys()))
        b = st.selectbox("Site B", list(site_map.keys()))
        planned = st.number_input("Longueur planifiée (km)", min_value=0.0, step=0.01)
        built = st.number_input("Longueur construite (km)", min_value=0.0, step=0.01)
        conduits = st.text_input("Conduites PEHD")
        chambers = st.number_input("Nb chambres", min_value=0, step=1)
        status = st.selectbox("Statut", ["Planned","In_Progress","Built","As_Built_Validated"])
        notes = st.text_area("Notes")
        if st.form_submit_button("💾 Enregistrer"):
            exec_sql("INSERT INTO fo_link(a_site_id,b_site_id,planned_length_km,built_length_km,pehd_conduits,chambers_count,status,notes) VALUES (?,?,?,?,?,?,?,?)",
                     (site_map[a], site_map[b], planned, built, conduits, int(chambers), status, notes))
            st.success("FO link enregistré.")
    st.dataframe(df("""
        SELECT l.fo_link_id, sa.site_code AS A, sb.site_code AS B, planned_length_km, built_length_km, status, pehd_conduits, chambers_count
        FROM fo_link l
        JOIN site sa ON sa.site_id=l.a_site_id
        JOIN site sb ON sb.site_id=l.b_site_id
        ORDER BY l.fo_link_id DESC
    """))

elif page=="FH Links":
    st.title("📡 FH Links")
    sites = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    site_map = {r["site_code"]:r["site_id"] for _,r in sites.iterrows()}
    with st.form("fh_form"):
        a = st.selectbox("Site A", list(site_map.keys()))
        b = st.selectbox("Site B", list(site_map.keys()))
        band = st.number_input("Bande (GHz)", min_value=0.0, step=0.1)
        bw = st.number_input("BW (MHz)", min_value=0, step=1)
        prot = st.selectbox("Protection", ["1+0","1+1","2+0","2+2","XPIC","HSB"])
        ant = st.number_input("Ø antenne (m)", min_value=0.0, step=0.1)
        rsl = st.number_input("RSL (dBm)", step=0.1)
        fade = st.number_input("Fade margin (dB)", step=0.1)
        avail = st.number_input("Objectif disponibilité (%)", min_value=0.0, max_value=100.0, step=0.001, value=99.9)
        notes = st.text_area("Notes")
        if st.form_submit_button("💾 Enregistrer"):
            exec_sql("INSERT INTO fh_link(a_site_id,b_site_id,band_GHz,channel_bw_MHz,protection,antenna_diameter_m,rsl_dbm,fade_margin_db,avail_target_pct,notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (site_map[a], site_map[b], band, int(bw), prot, ant, rsl, fade, avail, notes))
            st.success("FH link enregistré.")
    st.dataframe(df("""
        SELECT l.fh_link_id, sa.site_code AS A, sb.site_code AS B, band_GHz, channel_bw_MHz, protection, rsl_dbm, fade_margin_db, avail_target_pct
        FROM fh_link l
        JOIN site sa ON sa.site_id=l.a_site_id
        JOIN site sb ON sb.site_id=l.b_site_id
        ORDER BY l.fh_link_id DESC
    """))

elif page=="Énergie":
    st.title("⚡ Énergie")
    sites = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    site_map = {r["site_code"]:r["site_id"] for _,r in sites.iterrows()}
    with st.form("energy_form"):
        s = st.selectbox("Site", list(site_map.keys()))
        grid = st.selectbox("Réseau dispo ?", [0,1])
        ref = st.text_input("Référence compteur")
        sub = st.number_input("Abonnement (kVA)", min_value=0.0, step=0.1)
        solar = st.selectbox("Solaire hybride ?", [0,1])
        solar_p = st.number_input("Puissance solaire (kWp)", min_value=0.0, step=0.1)
        bat_type = st.text_input("Batteries (type)")
        bat_cnt = st.number_input("Batteries (nb)", min_value=0, step=1)
        bat_cap = st.number_input("Capacité (Ah)", min_value=0, step=1)
        genset = st.selectbox("Groupe électrogène ?", [0,1])
        genset_p = st.number_input("Puissance GE (kVA)", min_value=0.0, step=0.1)
        fuel = st.number_input("Cuve (L)", min_value=0, step=10)
        notes = st.text_area("Notes")
        if st.form_submit_button("💾 Enregistrer"):
            sid = site_map[s]
            ex = df("SELECT energy_id FROM energy_profile WHERE site_id=?", (sid,))
            if ex.empty:
                exec_sql("INSERT INTO energy_profile(site_id,grid_available,grid_reference,subscription_kVA,solar_hybrid,solar_power_kWp,batteries_type,batteries_count,batteries_capacity_Ah,genset_present,genset_power_kVA,fuel_tank_l,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (sid,int(grid),ref,sub,int(solar),solar_p,bat_type,int(bat_cnt),int(bat_cap),int(genset),genset_p,int(fuel),notes))
            else:
                exec_sql("UPDATE energy_profile SET grid_available=?, grid_reference=?, subscription_kVA=?, solar_hybrid=?, solar_power_kWp=?, batteries_type=?, batteries_count=?, batteries_capacity_Ah=?, genset_present=?, genset_power_kVA=?, fuel_tank_l=?, notes=? WHERE site_id=?",
                         (int(grid),ref,sub,int(solar),solar_p,bat_type,int(bat_cnt),int(bat_cap),int(genset),genset_p,int(fuel),notes,sid))
            st.success("Profil énergie enregistré.")
    st.dataframe(df("SELECT s.site_code, e.grid_available, e.solar_hybrid, e.subscription_kVA, e.genset_present, e.fuel_tank_l FROM energy_profile e JOIN site s ON s.site_id=e.site_id"))

elif page=="Datacom":
    st.title("🖧 Datacom")
    sites = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    site_map = {r["site_code"]:r["site_id"] for _,r in sites.iterrows()}
    with st.form("dc_form"):
        s = st.selectbox("Site", list(site_map.keys()))
        vendor = st.text_input("Vendor", value="Huawei")
        model = st.text_input("Modèle (ex: ATN910C)")
        role = st.selectbox("Rôle", ["access","aggregation","core","other"])
        ip = st.text_input("IP de gestion")
        notes = st.text_area("Notes")
        if st.form_submit_button("💾 Enregistrer"):
            exec_sql("INSERT INTO datacom_node(site_id,vendor,device_model,role,mgmt_ip,notes) VALUES (?,?,?,?,?,?)",
                     (site_map[s], vendor, model, role, ip, notes))
            st.success("Datacom enregistré.")
    st.dataframe(df("SELECT s.site_code, d.vendor, d.device_model, d.role, d.mgmt_ip FROM datacom_node d JOIN site s ON s.site_id=d.site_id ORDER BY s.site_code"))

elif page=="VSAT":
    st.title("🛰️ VSAT")
    sites = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    site_map = {r["site_code"]:r["site_id"] for _,r in sites.iterrows()}
    with st.form("vsat_form"):
        s = st.selectbox("Site", list(site_map.keys()))
        diam = st.number_input("Ø antenne (m)", min_value=0.0, step=0.1)
        lnb = st.text_input("LNB")
        buc = st.text_input("BUC")
        modem = st.text_input("Modem")
        ebno = st.number_input("Eb/N0 (dB)", step=0.1)
        esno = st.number_input("Es/N0 (dB)", step=0.1)
        notes = st.text_area("Notes")
        if st.form_submit_button("💾 Enregistrer"):
            exec_sql("INSERT INTO vsat_node(site_id,antenna_diameter_m,lnb_model,buc_model,modem_model,ebno_db,esno_db,notes) VALUES (?,?,?,?,?,?,?,?)",
                     (site_map[s], diam, lnb, buc, modem, ebno, esno, notes))
            st.success("VSAT enregistré.")
    st.dataframe(df("SELECT s.site_code, v.antenna_diameter_m, v.lnb_model, v.buc_model, v.modem_model, v.ebno_db, v.esno_db FROM vsat_node v JOIN site s ON s.site_id=v.site_id ORDER BY s.site_code"))

elif page=="Photos":
    st.title("🖼️ Photos")
    sites = df("SELECT site_id, site_code FROM site ORDER BY site_code")
    site_map = {r["site_code"]:r["site_id"] for _,r in sites.iterrows()}
    up = st.file_uploader("Uploader une photo (jpg/png)", type=["jpg","jpeg","png"])
    if up is not None:
        s = st.selectbox("Site", list(site_map.keys()))
        cat = st.selectbox("Catégorie", ["infrastructure","pylone_fh","fo","radio","energie","autre"])
        path = os.path.join(MEDIA_DIR, up.name)
        with open(path, "wb") as f:
            f.write(up.read())
        exec_sql("INSERT INTO photo(site_id,category,file_path,caption) VALUES (?,?,?,?)", (site_map[s], cat, path, up.name))
        st.success(f"Photo enregistrée → {path}")
    # liste
    ph = df("SELECT p.photo_id, s.site_code, p.category, p.file_path, p.caption FROM photo p JOIN site s ON s.site_id=p.site_id ORDER BY p.photo_id DESC")
    st.dataframe(ph)
    for _,r in ph.iterrows():
        st.write(f"{r['site_code']} • {r['category']} • {r['caption']}")
        if os.path.exists(r["file_path"]):
            st.image(r["file_path"])
