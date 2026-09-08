import os
import pandas as pd
from gdb_inspector import inspect_gdb_all
from report_generator import generate_excel_report

def test_full_pipeline():
    gdb_path = os.path.abspath("sample_test.gdb")
    print(f"Probando auditoria sobre GDB: {gdb_path}")
    
    def cb(val, msg):
        print(f"[{int(val*100)}%] {msg}")
        
    summary_df, fields_details_dict, gdfs_dict = inspect_gdb_all(gdb_path, progress_callback=cb)
    
    print("\n--- RESUMEN DE GDB ---")
    print(summary_df.to_string())
    
    print("\n--- DETALLE DE CAMPOS DE 'Estaciones_Monitoreo' ---")
    print(fields_details_dict['Estaciones_Monitoreo'].to_string())
    
    # Generar reporte Excel
    excel_bytes = generate_excel_report(summary_df, fields_details_dict, gdb_name="sample_test")
    report_filename = "test_output_report.xlsx"
    with open(report_filename, "wb") as f:
        f.write(excel_bytes)
        
    print(f"\nReporte Excel de prueba generado exitosamente: {os.path.abspath(report_filename)}")
    assert os.path.exists(report_filename) and os.path.getsize(report_filename) > 0
    assert len(summary_df) == 3
    print("SUCCESS: Prueba automatizada superada con exito!")

if __name__ == "__main__":
    test_full_pipeline()
