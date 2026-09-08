import os
import shutil
import tempfile
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium

from gdb_inspector import extract_zip_gdb, find_gdbs_in_directory, inspect_gdb_all
from report_generator import generate_excel_report

st.set_page_config(
    page_title="Auditor & Inspector de Geodatabases (.gdb)",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        color: #1F4E79;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #595959;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #1F4E79;
    }
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Título y Descripción
st.markdown('<div class="main-title">🗺️ Auditor y Revisor de Geodatabases (.gdb)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Herramienta integral para inspeccionar la estructura de Feature Classes, analizar atributos y detectar campos vacíos.</div>', unsafe_allow_html=True)

# Sidebar
st.sidebar.header("📁 Carga de Geodatabase")

target_gdb_path = None
temp_dir_to_clean = None

uploaded_file = st.sidebar.file_uploader(
    "Cargue un archivo .zip que contenga su carpeta .gdb:",
    type=["zip"],
    help="El archivo comprimido debe incluir la carpeta .gdb completa."
)
if uploaded_file is not None:
    if 'last_uploaded' not in st.session_state or st.session_state['last_uploaded'] != uploaded_file.name:
        with st.spinner("Descomprimiendo archivo ZIP..."):
            temp_dir, gdb_paths = extract_zip_gdb(uploaded_file)
            st.session_state['temp_dir'] = temp_dir
            st.session_state['gdb_paths'] = gdb_paths
            st.session_state['last_uploaded'] = uploaded_file.name
            
    if st.session_state.get('gdb_paths'):
        gdb_paths = st.session_state['gdb_paths']
        if len(gdb_paths) == 1:
            target_gdb_path = gdb_paths[0]
        else:
            target_gdb_path = st.sidebar.selectbox("Se encontraron varias GDBs en el ZIP. Seleccione una:", gdb_paths)
    else:
        st.sidebar.error("No se encontró ninguna carpeta .gdb dentro del archivo ZIP cargado.")

# Procesar Auditoría
if target_gdb_path:
    st.sidebar.success(f"GDB Seleccionada:\n`{os.path.basename(target_gdb_path)}`")
    
    if st.sidebar.button("🚀 Ejecutar Auditoría de GDB", type="primary") or 'audit_results' in st.session_state:
        
        # Ejecutar análisis si no está en caché o si cambió la GDB
        if 'audit_results' not in st.session_state or st.session_state.get('current_gdb') != target_gdb_path:
            progress_bar = st.progress(0, text="Iniciando análisis de Geodatabase...")
            def progress_update(val, msg):
                progress_bar.progress(val, text=msg)
                
            try:
                summary_df, fields_details_dict, gdfs_dict = inspect_gdb_all(target_gdb_path, progress_callback=progress_update)
                st.session_state['audit_results'] = (summary_df, fields_details_dict, gdfs_dict)
                st.session_state['current_gdb'] = target_gdb_path
                progress_bar.empty()
            except Exception as e:
                st.error(f"Error durante el procesamiento de la GDB: {e}")
                st.stop()
                
        summary_df, fields_details_dict, gdfs_dict = st.session_state['audit_results']
        
        # ---------------------------------------------------------
        # BANNER DE MÉTRICAS GENERALES
        # ---------------------------------------------------------
        total_fcs = len(summary_df)
        total_records = summary_df['Cant. Registros'].sum() if 'Cant. Registros' in summary_df else 0
        total_empty_cells = summary_df['Total Celdas Vacías'].sum() if 'Total Celdas Vacías' in summary_df else 0
        
        # Cálculo global de completitud
        total_attr_cells = 0
        for fc_name, fields_df in fields_details_dict.items():
            num_records = summary_df.loc[summary_df['Feature Class'] == fc_name, 'Cant. Registros'].values
            n_rec = num_records[0] if len(num_records) > 0 else 0
            total_attr_cells += (n_rec * len(fields_df))
            
        global_completeness = (100.0 * (1.0 - (total_empty_cells / total_attr_cells))) if total_attr_cells > 0 else 100.0
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Feature Classes", f"{total_fcs:,}")
        m2.metric("Registros Totales", f"{total_records:,}")
        m3.metric("Celdas Vacías Detectadas", f"{total_empty_cells:,}", delta=f"-{total_empty_cells:,}" if total_empty_cells > 0 else "0", delta_color="inverse")
        m4.metric("Salud Global de Datos", f"{global_completeness:.1f}%", delta=f"{global_completeness:.1f}%" if global_completeness >= 90 else f"{global_completeness:.1f}%", delta_color="normal")
        
        st.markdown("---")
        
        # ---------------------------------------------------------
        # PESTAÑAS DE NAVEGACIÓN Y AUDITORÍA
        # ---------------------------------------------------------
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Resumen General de GDB",
            "🔍 Inspector de Feature Class",
            "⚠️ Visor de Registros Incompletos",
            "🗺️ Mapa Interactivo",
            "📥 Exportar Reportes"
        ])
        
        # ---------------------------------------------------------
        # TAB 1: RESUMEN GENERAL DE GDB
        # ---------------------------------------------------------
        with tab1:
            st.subheader("Resumen de Salud por Feature Class")
            st.markdown("Tabla comparativa de la estructura y nivel de completitud de cada capa en la GDB.")
            
            # Formatear el DataFrame para visualización
            display_df = summary_df.copy()
            st.dataframe(
                display_df,
                column_config={
                    "% Completitud Capa": st.column_config.ProgressColumn(
                        "% Completitud",
                        format="%.2f%%",
                        min_value=0,
                        max_value=100
                    ),
                    "Cant. Registros": st.column_config.NumberColumn(format="%d"),
                    "Total Celdas Vacías": st.column_config.NumberColumn(format="%d"),
                },
                hide_index=True
            )
            
            # Gráfico de Barras de Completitud
            if not summary_df.empty:
                st.subheader("Porcentaje de Completitud por Feature Class")
                st.bar_chart(
                    summary_df.set_index('Feature Class')['% Completitud Capa'],
                    color="#1F4E79"
                )

        # ---------------------------------------------------------
        # TAB 2: INSPECTOR DE FEATURE CLASS (ESTRUCTURA DE CAMPOS)
        # ---------------------------------------------------------
        with tab2:
            st.subheader("Estructura de Atributos y Diagnóstico de Campos")
            
            selected_fc_t2 = st.selectbox(
                "Seleccione la Feature Class a auditar:",
                list(fields_details_dict.keys()),
                key="select_fc_tab2"
            )
            
            if selected_fc_t2:
                fields_df = fields_details_dict[selected_fc_t2]
                fc_info = summary_df[summary_df['Feature Class'] == selected_fc_t2].iloc[0]
                
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.info(f"**Geometría:** {fc_info['Tipo Geometría']}")
                col_b.info(f"**CRS:** {fc_info['Sistema de Coordenadas (CRS)']}")
                col_c.info(f"**Campos Totales:** {fc_info['Total Campos']}")
                col_d.warning(f"**Campos Incompletos:** {fc_info['Campos con Vacíos']}")
                
                filter_incomplete = st.checkbox("Mostrar únicamente campos con valores vacíos (pendientes por completar)", value=False)
                
                show_df = fields_df[fields_df['Estado'] == 'INCOMPLETO'] if filter_incomplete else fields_df
                
                st.dataframe(
                    show_df,
                    column_config={
                        "% Vacíos": st.column_config.NumberColumn(format="%.2f%%"),
                        "% Completitud": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100),
                        "Cant. Vacíos": st.column_config.NumberColumn(format="%d"),
                        "Cant. Llenos": st.column_config.NumberColumn(format="%d")
                    },
                    hide_index=True
                )

        # ---------------------------------------------------------
        # TAB 3: VISOR DE REGISTROS INCOMPLETOS
        # ---------------------------------------------------------
        with tab3:
            st.subheader("Filtrado de Filas/Entidades Incompletas")
            st.markdown("Examine exactamente cuáles registros de la tabla contienen atributos nulos o faltantes para su posterior corrección.")
            
            selected_fc_t3 = st.selectbox(
                "Seleccione la Feature Class:",
                list(gdfs_dict.keys()),
                key="select_fc_tab3"
            )
            
            if selected_fc_t3:
                gdf = gdfs_dict[selected_fc_t3]
                fields_df = fields_details_dict[selected_fc_t3]
                incomplete_field_names = fields_df[fields_df['Cant. Vacíos'] > 0]['Campo'].tolist()
                
                if not incomplete_field_names:
                    st.success("🎉 Esta Feature Class no contiene ninguna celda vacía. ¡Todos los datos están completos!")
                else:
                    selected_col_filter = st.selectbox(
                        "Seleccione el campo específico a inspeccionar:",
                        ["(Cualquier campo con vacíos)"] + incomplete_field_names
                    )
                    
                    # Función auxiliar para encontrar filas vacías
                    def is_empty_val(val):
                        if pd.isna(val) or val is None:
                            return True
                        if isinstance(val, str) and val.strip() == "":
                            return True
                        return False
                    
                    if selected_col_filter == "(Cualquier campo con vacíos)":
                        row_mask = gdf[incomplete_field_names].apply(lambda row: any(is_empty_val(x) for x in row), axis=1)
                    else:
                        row_mask = gdf[selected_col_filter].apply(is_empty_val)
                        
                    incomplete_rows = gdf[row_mask]
                    
                    st.warning(f"Se encontraron **{len(incomplete_rows)}** registros incompletos en esta Feature Class.")
                    
                    # Mostrar tabla sin la columna de geometría pesada
                    display_cols = [c for c in incomplete_rows.columns if c != 'geometry']
                    st.dataframe(incomplete_rows[display_cols])

        # ---------------------------------------------------------
        # TAB 4: MAPA INTERACTIVO
        # ---------------------------------------------------------
        with tab4:
            st.subheader("Visualización Geográfica de Entidades")
            
            selected_fc_t4 = st.selectbox(
                "Seleccione la Feature Class a visualizar:",
                list(gdfs_dict.keys()),
                key="select_fc_tab4"
            )
            
            if selected_fc_t4:
                gdf = gdfs_dict[selected_fc_t4]
                
                if 'geometry' not in gdf.columns or gdf.geometry.empty or gdf.geometry.dropna().empty:
                    st.info("Esta Feature Class es una tabla alfanumérica o no contiene geometrías válidas.")
                else:
                    try:
                        # Reproyectar a WGS84 (EPSG:4326) para folium
                        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
                            gdf_wgs84 = gdf.to_crs(epsg=4326)
                        else:
                            gdf_wgs84 = gdf.copy()
                            
                        # Limitar la cantidad de elementos en el mapa para mantener la fluidez
                        max_map_features = 500
                        if len(gdf_wgs84) > max_map_features:
                            st.caption(f"Mostrando los primeros {max_map_features} elementos de {len(gdf_wgs84)} para optimizar la visualización.")
                            gdf_map = gdf_wgs84.iloc[:max_map_features]
                        else:
                            gdf_map = gdf_wgs84
                            
                        # Calcular centro del mapa
                        bounds = gdf_map.total_bounds # [minx, miny, maxx, maxy]
                        center_lat = (bounds[1] + bounds[3]) / 2.0
                        center_lon = (bounds[0] + bounds[2]) / 2.0
                        
                        m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")
                        
                        # Agregar capa GeoJSON
                        popup_fields = [c for c in gdf_map.columns if c != 'geometry'][:5]
                        folium.GeoJson(
                            gdf_map,
                            name=selected_fc_t4,
                            tooltip=folium.GeoJsonTooltip(fields=popup_fields, aliases=popup_fields) if popup_fields else None
                        ).add_to(m)
                        
                        st_folium(m, width="stretch", height=500)
                        
                    except Exception as e:
                        st.error(f"No se pudo renderizar el mapa para esta capa: {e}")

        # ---------------------------------------------------------
        # TAB 5: EXPORTAR REPORTES
        # ---------------------------------------------------------
        with tab5:
            st.subheader("Descarga de Reportes Consolidados")
            st.markdown("Descargue el informe detallado en formato Excel o CSV para enviar al usuario o equipo responsable del llenado de datos.")
            
            gdb_basename = os.path.basename(target_gdb_path).replace(".gdb", "")
            
            # Generar Excel
            excel_bytes = generate_excel_report(summary_df, fields_details_dict, gdb_name=gdb_basename)
            
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                st.markdown("### 📊 Reporte Completo en Excel (.xlsx)")
                st.write("Incluye 3 hojas: Resumen de GDB, Matriz de Campos Incompletos y Estructura Completa de Atributos.")
                st.download_button(
                    label="📥 Descargar Reporte Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=f"Reporte_Revision_GDB_{gdb_basename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
                
            with col_exp2:
                st.markdown("### 📄 Resumen en Formato CSV (.csv)")
                st.write("Descarga un archivo plano con el resumen ejecutivo de todas las Feature Classes.")
                csv_bytes = summary_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Resumen CSV",
                    data=csv_bytes,
                    file_name=f"Resumen_GDB_{gdb_basename}.csv",
                    mime="text/csv"
                )
else:
    # Estado inicial cuando no se ha seleccionado ninguna GDB
    st.info("👈 Para comenzar, use el menú lateral izquierdo para cargar un archivo `.zip` con su Geodatabase o especificar la ruta local de la carpeta `.gdb`.")
