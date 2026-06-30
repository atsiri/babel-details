import streamlit as st
import pandas as pd
import networkx as nx
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components
from shapely import wkt
import geopandas as gpd
from streamlit_agraph import agraph, Node, Edge, Config

# --- 1. PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    placeholder = st.empty()
    with placeholder.container():
        st.write("## 🔒 Dashboard Login")
        if "APP_PASSWORD" not in st.secrets:
            st.warning("⚠️ 'APP_PASSWORD' not found in secrets.toml. allowing access for demo.")
            return True
            
        password = st.text_input("Password", type="password")
        if password:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                placeholder.empty()
                st.rerun()
            else:
                st.error("😕 Password incorrect")
    return False

if check_password():  

    # -------------------------
    # Page Configuration
    # -------------------------
    st.set_page_config(layout="wide", page_title="Mining Network & Area Dashboard")
    if 'map_key' not in st.session_state:
        st.session_state.map_key = 0
        
    # -------------------------
    # 1. Load Data
    # -------------------------
    @st.cache_data
    def load_data():
        df_network = pd.read_csv('network.csv')
        df_profile = pd.read_csv('profilenet.csv')
        df_wiup = pd.read_csv('wiup_babel.csv')
        
        # --- REVISED: Load Profil Mining Data ---
        df_profil_mining = pd.read_csv('profiles.csv')
        
        # Pre-process WIUP Geometry from WKT to Geopandas
        df_wiup['geometry'] = df_wiup['GEOMETRY'].apply(lambda x: wkt.loads(x) if pd.notna(x) else None)
        gdf_wiup = gpd.GeoDataFrame(df_wiup, geometry='geometry')
        
        # Clean company names and related fields for robust matching
        gdf_wiup['NAMA_PERUSAHAAN'] = gdf_wiup['NAMA_PERUSAHAAN'].astype(str).str.strip().str.upper()
        df_network['SOURCE'] = df_network['SOURCE'].astype(str).str.strip().str.upper()
        df_network['TARGET'] = df_network['TARGET'].astype(str).str.strip().str.upper()
        
        df_profile['NAMA_PERUSAHAAN'] = df_profile['NAMA_PERUSAHAAN'].astype(str).str.strip().str.upper()
        df_profile['NAMA'] = df_profile['NAMA'].astype(str).str.strip().str.upper()
        df_profile['KATEGORI'] = df_profile['KATEGORI'].astype(str).str.strip().str.upper()
        
        # --- REVISED: Clean Profil Mining Data ---
        if 'NAMA_PERUSAHAAN' in df_profil_mining.columns:
            df_profil_mining['NAMA_PERUSAHAAN'] = df_profil_mining['NAMA_PERUSAHAAN'].astype(str).str.strip().str.upper()
        
        return df_network, df_profile, gdf_wiup, df_profil_mining

    df_network, df_profile, gdf_wiup, df_profil_mining = load_data()

    # -------------------------
    # 2. Sidebar Filters
    # -------------------------
    st.sidebar.header("Filter Data")

    # Get unique values for filters, handling NaNs
    all_companies = sorted(list(set(gdf_wiup['NAMA_PERUSAHAAN'].dropna()) | set(df_network['SOURCE'].dropna())))
    all_cities = sorted(list(gdf_wiup['KABUPATEN'].dropna().unique()))
    all_commodities = sorted(list(gdf_wiup['KOMODITAS'].dropna().unique()))
    all_individuals = sorted(list(df_profile[df_profile['KATEGORI'] == 'INDIVIDU']['NAMA'].dropna().unique()))

    selected_company = st.sidebar.multiselect("Nama Perusahaan", options=all_companies)
    selected_nama = st.sidebar.multiselect("Nama Individu", options=all_individuals)
    selected_city = st.sidebar.multiselect("Kabupaten/Kota", options=all_cities)
    selected_commodity = st.sidebar.multiselect("Komoditas", options=all_commodities)

    # Logic to map selected individuals back to their companies
    companies_from_nama = []
    if selected_nama:
        companies_from_nama = df_profile[df_profile['NAMA'].isin(selected_nama)]['NAMA_PERUSAHAAN'].unique().tolist()
        companies_from_network = df_network[df_network['TARGET'].isin(selected_nama)]['SOURCE'].unique().tolist()
        companies_from_nama = list(set(companies_from_nama + companies_from_network))

    # Apply Filters to WIUP Data
    filtered_gdf = gdf_wiup.copy()
    
    # Filter by Company and/or Individual for Map
    if selected_company or selected_nama:
        valid_companies = set()
        if selected_company:
            valid_companies.update(selected_company)
        if selected_nama:
            valid_companies.update(companies_from_nama)
            
        filtered_gdf = filtered_gdf[filtered_gdf['NAMA_PERUSAHAAN'].isin(valid_companies)]
        
    if selected_city:
        filtered_gdf = filtered_gdf[filtered_gdf['KABUPATEN'].isin(selected_city)]
    if selected_commodity:
        filtered_gdf = filtered_gdf[filtered_gdf['KOMODITAS'].isin(selected_commodity)]

    # -------------------------
    # Layout Layout: Top Row
    # -------------------------
    st.title("Jejaring Tambang di Bangka Belitung")
    col1, col2 = st.columns(2)
            
    # -------------------------
    # 3. Top Left: Folium Map
    # -------------------------
    with col1:
        st.subheader("Peta Lokasi Tambang")
            
        if st.button("🔄 Reset Map Display"):
            st.session_state.map_key += 1
            st.rerun() 
            
        m = folium.Map(location=[-2.0, 106.0], zoom_start=7, tiles="CartoDB positron")
        network_companies = set(df_network['SOURCE'].dropna().unique()) | set(df_network['TARGET'].dropna().unique())
        
        if not filtered_gdf.empty:
            geo_json = filtered_gdf.to_json()
            
            def get_style(feature):
                props = feature['properties']
                
                company = str(props.get('NAMA_PERUSAHAAN', '')).strip().upper()
                status = str(props.get('STATUS_IUP', '')).strip().upper()
                komoditas = str(props.get('KOMODITAS', '')).strip().upper()
                
                is_in_network = company in network_companies
                
                dash_array = 'None' if is_in_network else '5, 5'
                weight = 2 if is_in_network else 1
                fill_opacity = 0.85 if is_in_network else 0.4
                fill_color = '#9E9E9E' 
                border_color = '#616161'
                
                timah_group = ['TIMAH', 'TIMAH DMP', 'BIJIH TIMAH', 'PASIR TIMAH']
                pasir_group = ['PASIR KUARSA', 'PASIR URUG', 'PASIR BANGUNAN', 'PASIR PASANG', 'KERIKIL BERPASIR ALAMI (SIRTU)', 'BATU KUARSA']
                kaolin_group = ['KAOLIN', 'TANAH LIAT']
                granit_zirkon_group = ['GRANIT', 'ZIRKON']
                
                if 'AKTIF' in status:
                    if komoditas in timah_group:
                        fill_color = '#0D47A1' if is_in_network else '#64B5F6'
                        border_color = '#0D47A1' if is_in_network else '#1976D2'
                    elif komoditas in pasir_group:
                        fill_color = '#E65100' if is_in_network else '#FFB74D'
                        border_color = '#E65100' if is_in_network else '#F57C00'
                    elif komoditas in kaolin_group:
                        fill_color = '#004D40' if is_in_network else '#4DB6AC'
                        border_color = '#004D40' if is_in_network else '#00897B'
                    elif komoditas in granit_zirkon_group:
                        fill_color = '#4A148C' if is_in_network else '#BA68C8'
                        border_color = '#4A148C' if is_in_network else '#8E24AA'
                    else:
                        fill_color = '#1B5E20' if is_in_network else '#81C784' 
                        border_color = '#1B5E20' if is_in_network else '#388E3C'
                        
                elif 'KADALUARSA' in status:
                    fill_color = '#B71C1C' if is_in_network else '#E57373' 
                    border_color = '#000000' if is_in_network else '#D32F2F'
                
                return {
                    'fillColor': fill_color, 'color': border_color, 'weight': weight,
                    'fillOpacity': fill_opacity, 'dashArray': dash_array
                }

            folium.GeoJson(
                geo_json, name="WIUP", style_function=get_style,
                highlight_function=lambda feature: {
                    'fillColor': '#FFEB3B', 'color': '#F57F17', 'weight': 3,
                    'fillOpacity': 0.9, 'dashArray': 'None'
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['NAMA_PERUSAHAAN', 'KABUPATEN', 'KOMODITAS', 'STATUS_IUP', 'LUAS_SK'],
                    aliases=['Company:', 'City:', 'Commodity:', 'Status:', 'Area (Ha):'],
                    localize=True
                )
            ).add_to(m)

        map_data = st_folium(m, height=600, width=800, returned_objects=["last_active_drawing"], key=f"map_{st.session_state.map_key}")
        
        clicked_company = None
        if map_data and map_data.get("last_active_drawing"):
            clicked_company = map_data["last_active_drawing"]["properties"].get("NAMA_PERUSAHAAN")
            st.success(f"Selected Company from Map: **{clicked_company}**")

    # -------------------------
    # 4. Top Right: Network Graph (REVISED using agraph for click events)
    # -------------------------
    with col2:
        st.subheader("Jejaring Perusahaan")
        
        G = nx.Graph() 
        for _, row in df_network.iterrows():
            G.add_edge(row['SOURCE'], row['TARGET'], position=row['POSITION'], category=row['CATEGORY'])

        nodes_to_draw = set(G.nodes())

        if clicked_company and clicked_company in G.nodes():
            nodes_to_draw = nx.node_connected_component(G, clicked_company)
        elif selected_company or selected_nama:
            nodes_to_draw = set()
            nodes_to_check = []
            
            if selected_company:
                nodes_to_check.extend(selected_company)
            if selected_nama:
                nodes_to_check.extend(selected_nama) 
                
            for node in nodes_to_check:
                if node in G.nodes():
                    nodes_to_draw.update(nx.node_connected_component(G, node))

        # --- REVISED: Use Streamlit-Agraph so clicks return directly to Streamlit ---
        nodes = []
        edges = []
        added_nodes = set()
        
        for source, target, data in G.edges(data=True):
            if source in nodes_to_draw and target in nodes_to_draw:
                category = str(data.get('category', 'INDIVIDU')).upper()
                position = str(data.get('position', ''))

                if source not in added_nodes:
                    nodes.append(Node(id=source, label=source, title=source, shape='box', color='#4CAF50', size=25))
                    added_nodes.add(source)

                if target not in added_nodes:
                    if category == 'PERUSAHAAN':
                        node_shape, node_color = 'box', '#2196F3'
                    else:
                        node_shape, node_color = 'dot', '#FF9800' 
                        
                    nodes.append(Node(id=target, label=target, title=f"{target}\nPosition: {position}", shape=node_shape, color=node_color, size=25))
                    added_nodes.add(target)

                edges.append(Edge(source=source, target=target, title=f"{source}\nPosition: {position}"))
                
        # Generate interactive Graph that returns user clicks
        config = Config(width="100%", height=600, directed=True, physics=True)
        clicked_node = agraph(nodes=nodes, edges=edges, config=config)
        
        if clicked_node:
            st.success(f"Selected Node from Graph: **{clicked_node}**")

    # -------------------------
    # Layout: Bottom Data Tables (REVISED logic for Unified Interactivity)
    # -------------------------
    st.markdown("---")
    st.subheader("Details")

    # Determine Focus Companies unifying Map Click, Graph Click, and Filter
    focus_companies = set()
    
    if clicked_company:
        focus_companies.add(clicked_company)
        
    if clicked_node:
        focus_companies.add(clicked_node)
        # If the clicked node is an individual, fetch associated companies automatically
        assoc_comps_profile = df_profile[df_profile['NAMA'] == clicked_node]['NAMA_PERUSAHAAN'].unique().tolist()
        assoc_comps_network = df_network[df_network['TARGET'] == clicked_node]['SOURCE'].unique().tolist()
        focus_companies.update(assoc_comps_profile)
        focus_companies.update(assoc_comps_network)

    if selected_company or selected_nama:
        if selected_company:
            focus_companies.update(selected_company)
        if selected_nama:
            focus_companies.update(companies_from_nama)

    # Display 3 Tabs
    tab1, tab2, tab3 = st.tabs(["Data WIUP", "Data Jejaring Perusahaan", "Profil Perusahaan"])

    with tab1:
        if focus_companies:
            st.write(f"Detail WIUP (Berdasarkan Pilihan Peta/Jejaring/Filter)")
            wiup_view = filtered_gdf[filtered_gdf['NAMA_PERUSAHAAN'].isin(focus_companies)]
        else:
            st.write("Detail WIUP Area")
            wiup_view = filtered_gdf

        display_gdf = wiup_view.drop(columns=['geometry', 'GEOMETRY'], errors='ignore')
        st.dataframe(display_gdf, use_container_width=True)

    with tab2:
        st.write("Detail Jejaring Perusahaan:")
        profile_view = df_profile[['NAMA_PERUSAHAAN', 'NAMA', 'JABATAN', 'NOMOR_IDENTITAS', 'NPWP', 'KATEGORI']].copy()
        
        if focus_companies:
            profile_view = profile_view[profile_view['NAMA_PERUSAHAAN'].isin(focus_companies)]
            
        st.dataframe(profile_view, use_container_width=True)

    # --- REVISED: New Profil Mining Tab ---
    with tab3:
        st.write("Profil Perusahaan:")
        profil_mining_view = df_profil_mining[['NAMA_PERUSAHAAN', 'NIB', 'ALAMAT', 'NO_TELP', 'NPWP',
       'JENIS_PERUSAHAAN', 'STATUS_NIB']].copy()
        
        if focus_companies:
            profil_mining_view = profil_mining_view[profil_mining_view['NAMA_PERUSAHAAN'].isin(focus_companies)]
            
        st.dataframe(profil_mining_view, use_container_width=True)