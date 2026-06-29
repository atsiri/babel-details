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
    # NOTE: If you just want to run this without password, change this function to return True immediately.
    # return True 
    
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    placeholder = st.empty()
    with placeholder.container():
        st.write("## 🔒 Dashboard Login")
        # Defaulting to a simple check if secrets are not set up, for demonstration purposes
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
    # --- ADDED: Initialize Session State for Map Key ---
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
        
        # Pre-process WIUP Geometry from WKT to Geopandas
        df_wiup['geometry'] = df_wiup['GEOMETRY'].apply(lambda x: wkt.loads(x) if pd.notna(x) else None)
        gdf_wiup = gpd.GeoDataFrame(df_wiup, geometry='geometry')
        
        # Clean company names for robust matching
        gdf_wiup['NAMA_PERUSAHAAN'] = gdf_wiup['NAMA_PERUSAHAAN'].astype(str).str.strip().str.upper()
        df_network['SOURCE'] = df_network['SOURCE'].astype(str).str.strip().str.upper()
        df_network['TARGET'] = df_network['TARGET'].astype(str).str.strip().str.upper()
        df_profile['NAMA_PERUSAHAAN'] = df_profile['NAMA_PERUSAHAAN'].astype(str).str.strip().str.upper()
        
        return df_network, df_profile, gdf_wiup

    df_network, df_profile, gdf_wiup = load_data()

    # -------------------------
    # 2. Sidebar Filters
    # -------------------------
    st.sidebar.header("Filter Data")

    # Get unique values for filters, handling NaNs
    all_companies = sorted(list(set(gdf_wiup['NAMA_PERUSAHAAN'].dropna()) | set(df_network['SOURCE'].dropna())))
    all_cities = sorted(list(gdf_wiup['KABUPATEN'].dropna().unique()))
    all_commodities = sorted(list(gdf_wiup['KOMODITAS'].dropna().unique()))

    selected_company = st.sidebar.multiselect("Nama Perusahaan", options=all_companies)
    selected_city = st.sidebar.multiselect("Kabupaten/Kota", options=all_cities)
    selected_commodity = st.sidebar.multiselect("Komoditas", options=all_commodities)

    # Apply Filters to WIUP Data
    filtered_gdf = gdf_wiup.copy()
    if selected_company:
        filtered_gdf = filtered_gdf[filtered_gdf['NAMA_PERUSAHAAN'].isin(selected_company)]
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
            
        # --- ADDED: Reset Button ---
        if st.button("🔄 Reset Map Display"):
            st.session_state.map_key += 1  # Change the key to force map reload
            st.rerun()                     # Refresh the app immediately
            
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
                
                # Default style (Tidak di network: Warna terang, garis putus-putus. Di network: Gelap, garis solid)
                dash_array = 'None' if is_in_network else '5, 5'
                weight = 2 if is_in_network else 1
                fill_opacity = 0.85 if is_in_network else 0.4
                
                fill_color = '#9E9E9E' 
                border_color = '#616161'
                
                # Pengelompokan Komoditas berdasarkan list data
                timah_group = ['TIMAH', 'TIMAH DMP', 'BIJIH TIMAH', 'PASIR TIMAH']
                pasir_group = ['PASIR KUARSA', 'PASIR URUG', 'PASIR BANGUNAN', 'PASIR PASANG', 'KERIKIL BERPASIR ALAMI (SIRTU)', 'BATU KUARSA']
                kaolin_group = ['KAOLIN', 'TANAH LIAT']
                granit_zirkon_group = ['GRANIT', 'ZIRKON']
                
                if 'AKTIF' in status:
                    if komoditas in timah_group:
                        fill_color = '#0D47A1' if is_in_network else '#64B5F6' # Biru
                        border_color = '#0D47A1' if is_in_network else '#1976D2'
                    elif komoditas in pasir_group:
                        fill_color = '#E65100' if is_in_network else '#FFB74D' # Oranye
                        border_color = '#E65100' if is_in_network else '#F57C00'
                    elif komoditas in kaolin_group:
                        fill_color = '#004D40' if is_in_network else '#4DB6AC' # Teal / Hijau Tosca
                        border_color = '#004D40' if is_in_network else '#00897B'
                    elif komoditas in granit_zirkon_group:
                        fill_color = '#4A148C' if is_in_network else '#BA68C8' # Ungu
                        border_color = '#4A148C' if is_in_network else '#8E24AA'
                    else:
                        # Default untuk komoditas lain (Hijau)
                        fill_color = '#1B5E20' if is_in_network else '#81C784' 
                        border_color = '#1B5E20' if is_in_network else '#388E3C'
                        
                elif 'KADALUARSA' in status:
                    # Merah untuk status KADALUARSA
                    fill_color = '#B71C1C' if is_in_network else '#E57373' 
                    border_color = '#000000' if is_in_network else '#D32F2F'
                
                return {
                    'fillColor': fill_color,
                    'color': border_color,
                    'weight': weight,
                    'fillOpacity': fill_opacity,
                    'dashArray': dash_array
                }

            folium.GeoJson(
                geo_json,
                name="WIUP",
                style_function=get_style,
                highlight_function=lambda feature: {
                    'fillColor': '#FFEB3B',
                    'color': '#F57F17',
                    'weight': 3,
                    'fillOpacity': 0.9,
                    'dashArray': 'None'
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['NAMA_PERUSAHAAN', 'KABUPATEN', 'KOMODITAS', 'STATUS_IUP', 'LUAS_SK'],
                    aliases=['Company:', 'City:', 'Commodity:', 'Status:', 'Area (Ha):'],
                    localize=True
                )
            ).add_to(m)

        map_data = st_folium(m, height=600, width=800, returned_objects=["last_active_drawing"])
        
        clicked_company = None
        if map_data and map_data.get("last_active_drawing"):
            clicked_company = map_data["last_active_drawing"]["properties"].get("NAMA_PERUSAHAAN")
            st.success(f"Selected Company from Map: **{clicked_company}**")

    # -------------------------
    # 4. Top Right: Network Graph
    # -------------------------
    with col2:
        st.subheader("Jejaring Perusahaan")
        
        # Build complete NetworkX Graph
        G = nx.Graph() # Undirected to allow traversal in any direction
        for _, row in df_network.iterrows():
            G.add_edge(row['SOURCE'], row['TARGET'], position=row['POSITION'], category=row['CATEGORY'])

        nodes_to_draw = set(G.nodes())

        # If a company is clicked on the map, filter graph to show all connected nodes (all degrees)
        if clicked_company and clicked_company in G.nodes():
            # Get the connected component containing the clicked company
            connected_subgraph_nodes = nx.node_connected_component(G, clicked_company)
            nodes_to_draw = connected_subgraph_nodes
        elif selected_company:
            # If filtered by sidebar instead
            nodes_to_draw = set()
            for comp in selected_company:
                if comp in G.nodes():
                    nodes_to_draw.update(nx.node_connected_component(G, comp))

        # Create Pyvis network from the filtered nodes
        from pyvis.network import Network
        net = Network(height='600px', width='100%', directed=True, bgcolor='#ffffff', font_color='black')
        
        added_nodes = set()
        for source, target, data in G.edges(data=True):
            if source in nodes_to_draw and target in nodes_to_draw:
                category = str(data.get('category', 'INDIVIDU')).upper()
                position = str(data.get('position', ''))
                
                # # Add Source
                # if source not in added_nodes:
                #     net.add_node(source, label=source, title="Source Company", shape='square', color='#4CAF50', size=30)
                #     added_nodes.add(source)
                    
                # # Add Target
                # if target not in added_nodes:
                #     shape = 'square' if category == 'PERUSAHAAN' else 'dot'
                #     color = '#2196F3' if category == 'PERUSAHAAN' else '#FF9800'
                #     net.add_node(target, label=target, title=f"Cat: {category}\nPos: {position}", shape=shape, color=color, size=20)
                #     added_nodes.add(target)
                    
                # net.add_edge(source, target, title=f"Pos: {position}")

                # Add SOURCE node
                if source not in added_nodes:
                    net.add_node(
                        source, 
                        label=source, 
                        title=source, 
                        shape='square', 
                        color='#4CAF50',
                        size=5,               
                        font={'size': 15}      
                    )
                    added_nodes.add(source)

                # Add TARGET node
                if target not in added_nodes:
                    if category == 'PERUSAHAAN':
                        node_shape = 'square'
                        node_color = '#2196F3'
                    else:
                        node_shape = 'dot' 
                        node_color = '#FF9800' 
                        
                    net.add_node(
                        target, 
                        label=target, 
                        title=f"{target}\nPosition: {position}", 
                        shape=node_shape, 
                        color=node_color,
                        size=5,               
                        font={'size': 15}      
                    )
                    added_nodes.add(target)

                # Format the hover text details for the edge
                edge_hover_details = f"{source}\nPosition: {position}"

                # Add an edge
                # REMOVED: label=position (so it doesn't show permanently)
                # ADDED: title=edge_hover_details (so it shows on hover)
                net.add_edge(
                    source, 
                    target, 
                    title=edge_hover_details
                )
                
        # Generate and display Graph
        net.save_graph("temp_network.html")
        with open("temp_network.html", 'r', encoding='utf-8') as f:
            components.html(f.read(), height=620)

    # -------------------------
    # Layout: Bottom Data Tables
    # -------------------------
    st.markdown("---")
    st.subheader("Details")

    tab1, tab2 = st.tabs(["Data WIUP", "Data Jejaring Perusahaan"])

    with tab1:
        # 1. Dynamic logic for the WIUP table based on map clicks
        if clicked_company:
            st.write(f"Detail WIUP {clicked_company}**")
            # Filter to only show the clicked company
            wiup_view = filtered_gdf[filtered_gdf['NAMA_PERUSAHAAN'] == clicked_company]
        else:
            st.write("Detail WIUP Area")
            # Show all data (still respects sidebar filters)
            wiup_view = filtered_gdf

        # Drop geometry columns for clean tabular viewing
        # Using errors='ignore' in case they are already dropped
        display_gdf = wiup_view.drop(columns=['geometry', 'GEOMETRY'], errors='ignore')
        st.dataframe(display_gdf, use_container_width=True)

    with tab2:
        st.write("Detail Jejaring Perusahaan:")
        # Filter profile data based on map selection or sidebar
        #profile_view = df_profile.copy()
        profile_view = df_profile[['NAMA_PERUSAHAAN', 'NAMA', 'JABATAN', 'NOMOR_IDENTITAS', 'NPWP', 'KATEGORI']]
        if clicked_company:
            st.write(f"Detail Jejaring Perusahaan **{clicked_company}**")
            profile_view = profile_view[profile_view['NAMA_PERUSAHAAN'] == clicked_company]
        elif selected_company:
            profile_view = profile_view[profile_view['NAMA_PERUSAHAAN'].isin(selected_company)]
            
        st.dataframe(profile_view, use_container_width=True)
        