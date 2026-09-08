import os
import shutil
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
import pandas as pd
import numpy as np

def create_sample_gdb(gdb_path="sample_test.gdb"):
    """
    Crea una Geodatabase (.gdb) de prueba con 3 Feature Classes conteniendo
    geometrías de Puntos, Líneas y Polígonos con valores intencionalmente nulos y vacíos.
    """
    if os.path.exists(gdb_path):
        shutil.rmtree(gdb_path)
        
    print(f"Creando GDB de muestra en: {gdb_path}")
    
    # 1. Feature Class Puntos: "Estaciones_Monitoreo"
    pts_data = {
        'id_estacion': [101, 102, 103, 104, 105],
        'nombre_estacion': ["Estación Norte", "Estación Sur", "", None, "Estación Central"],
        'operador': ["Empresa A", "Empresa B", "  ", None, "Empresa A"],
        'caudal_m3s': [12.5, None, 8.4, 15.0, None],
        'estado_revision': ["Aprobado", "Pendiente", None, "", "Aprobado"],
        'geometry': [
            Point(-70.65, -33.45),
            Point(-70.66, -33.46),
            Point(-70.64, -33.44),
            Point(-70.67, -33.47),
            Point(-70.63, -33.43)
        ]
    }
    gdf_pts = gpd.GeoDataFrame(pts_data, crs="EPSG:4326")
    gdf_pts.to_file(gdb_path, driver="OpenFileGDB", layer="Estaciones_Monitoreo")
    print(" -> Creada capa 'Estaciones_Monitoreo' (Puntos)")

    # 2. Feature Class Líneas: "Red_Vial"
    lines_data = {
        'id_tramo': [1, 2, 3, 4],
        'nombre_via': ["Av. Principal", None, "Calle Secundaria", "Pasaje Central"],
        'tipo_pavimento': ["Asfalto", "Hormigón", "", None],
        'ancho_metros': [12.0, 8.5, None, 6.0],
        'geometry': [
            LineString([(-70.65, -33.45), (-70.64, -33.44)]),
            LineString([(-70.66, -33.46), (-70.65, -33.45)]),
            LineString([(-70.64, -33.44), (-70.63, -33.43)]),
            LineString([(-70.67, -33.47), (-70.66, -33.46)])
        ]
    }
    gdf_lines = gpd.GeoDataFrame(lines_data, crs="EPSG:4326")
    gdf_lines.to_file(gdb_path, driver="OpenFileGDB", layer="Red_Vial")
    print(" -> Creada capa 'Red_Vial' (Líneas)")

    # 3. Feature Class Polígonos: "Predios_Urbanos"
    poly_data = {
        'rol_predio': ["001-05", "001-06", "001-07"],
        'propietario': ["Juan Pérez", None, "María Gómez"],
        'uso_suelo': ["Residencial", "Comercial", ""],
        'avaluo_usd': [150000.0, 230000.0, None],
        'geometry': [
            Polygon([(-70.65, -33.45), (-70.64, -33.45), (-70.64, -33.44), (-70.65, -33.44)]),
            Polygon([(-70.66, -33.46), (-70.65, -33.46), (-70.65, -33.45), (-70.66, -33.45)]),
            Polygon([(-70.64, -33.44), (-70.63, -33.44), (-70.63, -33.43), (-70.64, -33.43)])
        ]
    }
    gdf_polys = gpd.GeoDataFrame(poly_data, crs="EPSG:4326")
    gdf_polys.to_file(gdb_path, driver="OpenFileGDB", layer="Predios_Urbanos")
    print(" -> Creada capa 'Predios_Urbanos' (Polígonos)")

    print("¡Geodatabase de prueba creada exitosamente!")
    return gdb_path

if __name__ == "__main__":
    create_sample_gdb()
