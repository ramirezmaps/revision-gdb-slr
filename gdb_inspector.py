import os
import zipfile
import tempfile
import pandas as pd
import geopandas as gpd
import pyogrio
import fiona

def extract_zip_gdb(zip_file_source):
    """
    Extrae un archivo ZIP subido a un directorio temporal y busca carpetas .gdb.
    Retorna la ruta temporal y la ruta de la primera GDB encontrada.
    """
    temp_dir = tempfile.mkdtemp()
    
    if isinstance(zip_file_source, str):
        with zipfile.ZipFile(zip_file_source, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
    else:
        # Streamlit UploadedFile object
        with zipfile.ZipFile(zip_file_source, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
    gdb_paths = find_gdbs_in_directory(temp_dir)
    return temp_dir, gdb_paths

def find_gdbs_in_directory(directory):
    """
    Busca todas las carpetas .gdb dentro de un directorio dado.
    """
    gdb_paths = []
    for root, dirs, files in os.walk(directory):
        for d in dirs:
            if d.lower().endswith('.gdb'):
                gdb_paths.append(os.path.join(root, d))
    return gdb_paths

def get_gdb_layers(gdb_path):
    """
    Obtiene la lista de Feature Classes (capas) en la Geodatabase.
    """
    try:
        layers_info = pyogrio.list_layers(gdb_path)
        # pyogrio list_layers devuelve un ndarray/matriz con [nombre_capa, tipo_geometria]
        layers = []
        for l_info in layers_info:
            layers.append({
                'name': l_info[0],
                'geom_type': l_info[1]
            })
        return layers
    except Exception:
        try:
            layer_names = fiona.listlayers(gdb_path)
            return [{'name': name, 'geom_type': 'Unknown'} for name in layer_names]
        except Exception as e:
            raise RuntimeError(f"Error al listar capas de la GDB {gdb_path}: {e}")

def is_cell_empty(val):
    """
    Evalúa si un valor se considera vacío (NaN, None, "", espacio en blanco o pd.NA).
    """
    if pd.isna(val) or val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False

def inspect_feature_class(gdb_path, layer_name):
    """
    Analiza una Feature Class específica:
    - Carga GeoDataFrame
    - Extrae CRS y metadatos de geometría
    - Analiza valores nulos/vacíos campo por campo
    """
    gdf = gpd.read_file(gdb_path, layer=layer_name)
    total_records = len(gdf)
    
    # CRS Info
    crs_name = "Sin CRS definido"
    if gdf.crs is not None:
        crs_name = gdf.crs.name if gdf.crs.name else str(gdf.crs)
        if gdf.crs.to_epsg():
            crs_name += f" (EPSG:{gdf.crs.to_epsg()})"
            
    # Geometry type
    geom_types = gdf.geometry.geom_type.unique().tolist() if 'geometry' in gdf.columns and not gdf.geometry.empty else ["Sin Geometría"]
    geom_str = ", ".join([str(g) for g in geom_types if g is not None])
    
    # Columns to inspect (excluyendo 'geometry')
    attr_cols = [c for c in gdf.columns if c != 'geometry']
    
    fields_report = []
    total_empty_cells_layer = 0
    cols_with_empty = 0
    
    for col in attr_cols:
        series = gdf[col]
        # Conteo de vacíos estricto (incluyendo strings vacías)
        empty_mask = series.apply(is_cell_empty)
        empty_count = int(empty_mask.sum())
        total_empty_cells_layer += empty_count
        
        if empty_count > 0:
            cols_with_empty += 1
            
        empty_pct = (empty_count / total_records * 100.0) if total_records > 0 else 0.0
        unique_count = int(series.nunique(dropna=True))
        
        # Muestra de valores no nulos
        non_null_samples = series[~empty_mask].head(3).tolist()
        sample_str = ", ".join([str(x) for x in non_null_samples]) if non_null_samples else "N/A (Sin Datos)"
        
        fields_report.append({
            'Campo': col,
            'Tipo de Dato': str(series.dtype),
            'Estado': 'COMPLETO' if empty_count == 0 else 'INCOMPLETO',
            'Cant. Vacíos': empty_count,
            '% Vacíos': round(empty_pct, 2),
            'Cant. Llenos': total_records - empty_count,
            '% Completitud': round(100.0 - empty_pct, 2),
            'Valores Únicos': unique_count,
            'Ejemplos de Datos': sample_str
        })
        
    fields_df = pd.DataFrame(fields_report)
    
    # Métricas de resumen de la capa
    total_cells = total_records * len(attr_cols)
    completeness_pct = (100.0 * (1.0 - (total_empty_cells_layer / total_cells))) if total_cells > 0 else 100.0
    
    layer_summary = {
        'Feature Class': layer_name,
        'Tipo Geometría': geom_str,
        'Sistema de Coordenadas (CRS)': crs_name,
        'Cant. Registros': total_records,
        'Total Campos': len(attr_cols),
        'Campos con Vacíos': cols_with_empty,
        'Campos Completos': len(attr_cols) - cols_with_empty,
        'Total Celdas Vacías': total_empty_cells_layer,
        '% Completitud Capa': round(completeness_pct, 2)
    }
    
    return layer_summary, fields_df, gdf

def inspect_gdb_all(gdb_path, progress_callback=None):
    """
    Recorre todas las capas de una GDB y genera resúmenes y estadísticas consolidadas.
    """
    layers = get_gdb_layers(gdb_path)
    total_layers = len(layers)
    
    gdb_summaries = []
    all_fields_details = {}
    gdfs_dict = {}
    
    for idx, layer_info in enumerate(layers):
        l_name = layer_info['name']
        if progress_callback:
            progress_callback(idx / total_layers, f"Procesando Feature Class: {l_name} ({idx+1}/{total_layers})")
            
        try:
            l_summary, fields_df, gdf = inspect_feature_class(gdb_path, l_name)
            gdb_summaries.append(l_summary)
            all_fields_details[l_name] = fields_df
            gdfs_dict[l_name] = gdf
        except Exception as e:
            gdb_summaries.append({
                'Feature Class': l_name,
                'Tipo Geometría': layer_info.get('geom_type', 'Error'),
                'Sistema de Coordenadas (CRS)': 'Error al leer',
                'Cant. Registros': 0,
                'Total Campos': 0,
                'Campos con Vacíos': 0,
                'Campos Completos': 0,
                'Total Celdas Vacías': 0,
                '% Completitud Capa': 0.0,
                'Error': str(e)
            })
            
    if progress_callback:
        progress_callback(1.0, "Análisis completado exitosamente.")
        
    summary_df = pd.DataFrame(gdb_summaries)
    return summary_df, all_fields_details, gdfs_dict
