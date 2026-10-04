import streamlit as st
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
from prophet import Prophet

# === CONFIGURACIÓN DE LA PÁGINA ===
st.set_page_config(
    page_title="Chef.AI Dashboard",
    page_icon="🍽️",
    layout="wide"
)

# === NOMBRES DE ARCHIVOS ===
FILE_VENTAS = "ventas_restaurante_agosto.csv"
FILE_RENTABILIDAD = "rentabilidad_platos.xlsx"
FILE_BIBLIOTECA = "biblioteca_ingredientes.xlsx"

# === FUNCIÓN PARA CARGAR DATOS DE VENTAS (CSV) (NUEVA) ===
@st.cache_data # Podemos cachear este, ya que no se modifica
def load_sales_data(file_name):
    """Carga y procesa el archivo CSV de ventas."""
    if not os.path.exists(file_name):
        st.error(f"No se encontró el archivo principal '{file_name}'.")
        st.info("Asegúrate de tener el archivo 'ventas_restaurante_agosto.csv' en la misma carpeta.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(file_name)
        # Limpia cualquier texto erróneo antes de convertir a fecha
        df['Fecha'] = df['Fecha'].str.split(' ').str[0]
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        # Elimina filas donde la fecha no se pudo parsear
        df = df.dropna(subset=['Fecha']) 
        return df
    except Exception as e:
        st.error(f"Error al leer {file_name}: {e}")
        return pd.DataFrame()

# === FUNCIÓN PARA CARGAR DATOS (EXCEL) (CORREGIDA) ===
def load_data(file_name):
    """Carga un archivo Excel. Si no existe, devuelve un DataFrame vacío."""
    if os.path.exists(file_name):
        try:
            df = pd.read_excel(file_name)
            return df
        except Exception as e:
            st.error(f"Error al leer {file_name}: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Cargar datos principales de ventas
df_ventas = load_sales_data(FILE_VENTAS) # <-- USA LA NUEVA FUNCIÓN

if df_ventas.empty:
    st.stop() # El error ya se muestra dentro de la función load_sales_data

# === MENÚ LATERAL ===
st.sidebar.title("🍴 Chef.AI Panel")
opcion = st.sidebar.radio(
    "Selecciona una vista:",
    (
        "📊 Métricas Generales",
        "💰 Rentabilidad y Costos",
        "📈 Análisis de Menú", 
        "🤖 Predicción de Demanda",
    )
)

# === 1️⃣ MÉTRICAS GENERALES ===
if opcion == "📊 Métricas Generales":
    st.title("📈 Métricas Generales del Restaurante")

    total_ventas = df_ventas["Total Venta (€)"].sum()
    total_platos = df_ventas["Cantidad"].sum()
    platos_mas_vendidos = df_ventas.groupby("Producto")["Cantidad"].sum().sort_values(ascending=False).head(5)
    # Agrupar por fecha (día)
    ventas_por_dia = df_ventas.groupby(df_ventas['Fecha'].dt.date)["Total Venta (€)"].sum()

    col1, col2 = st.columns(2)
    col1.metric("💰 Total de Ventas", f"{total_ventas:,.2f} €")
    col2.metric("🍽️ Nº Total de Platos Vendidos", int(total_platos))

    st.subheader("🥇 Platos más vendidos (Top 5)")
    st.bar_chart(platos_mas_vendidos)

    st.subheader("📆 Evolución de Ventas por Día")
    st.line_chart(ventas_por_dia)

    # === BLOQUE: Mostrar rentabilidad (del archivo guardado) ===
    st.markdown("---")
    st.subheader("💰 Resumen de Rentabilidad por Plato")

    df_rent = load_data(FILE_RENTABILIDAD) # <-- Usa la función simple de Excel

    if not df_rent.empty:
        # Asegurarse de que las columnas esperadas existen
        columnas_rent = ["Plato", "Costo Ingredientes (€)", "Precio Venta Medio (€)", "Beneficio (€)", "Margen (%)"]
        if all(col in df_rent.columns for col in columnas_rent):
            st.dataframe(df_rent[columnas_rent], use_container_width=True)

            # Métricas globales de rentabilidad
            mapa_cantidad = df_ventas.groupby("Producto")["Cantidad"].sum()
            df_rent_con_cantidad = df_rent.join(mapa_cantidad, on="Plato", how="left").fillna(0)
            
            beneficio_total_platos = (df_rent_con_cantidad["Beneficio (€)"] * df_rent_con_cantidad["Cantidad"]).sum()
            
            if df_rent_con_cantidad["Cantidad"].sum() > 0:
                margen_ponderado = (df_rent_con_cantidad["Margen (%)"] * df_rent_con_cantidad["Cantidad"]).sum() / df_rent_con_cantidad["Cantidad"].sum()
            else:
                margen_ponderado = df_rent_con_cantidad["Margen (%)"].mean() if not df_rent_con_cantidad.empty else 0

            st.metric("🏆 Beneficio total estimado (basado en ventas)", f"{beneficio_total_platos:,.2f} €")
            st.metric("📊 Margen medio ponderado (por ventas)", f"{margen_ponderado:.1f} %")
        else:
            st.warning(f"El archivo {FILE_RENTABILIDAD} no tiene las columnas esperadas.")
            st.dataframe(df_rent)
    else:
        st.info(f"Aún no se ha calculado la rentabilidad de ningún plato. Ve a la sección '💰 Rentabilidad y Costos'.")


# === 2️⃣ CALCULADORA DE RENTABILIDAD (Mejorada) ===
elif opcion == "💰 Rentabilidad y Costos":
    st.title("💰 Gestión de Costos y Rentabilidad")
    st.info("Sigue los pasos: 1. Añade ingredientes a tu biblioteca. 2. Define la receta de un plato y calcula su rentabilidad.")

    # --- PARTE 1: BIBLIOTECA DE INGREDIENTES ---
    st.markdown("---")
    st.subheader("1. 📚 Biblioteca de Ingredientes")
    st.caption("Añade aquí los ingredientes que compras y su precio.")

    df_biblioteca = load_data(FILE_BIBLIOTECA) # <-- Usa la función simple de Excel

    with st.form("form_ingrediente"):
        col1, col2, col3 = st.columns(3)
        nombre_ing = col1.text_input("Nombre del Ingrediente (ej. Patatas)")
        unidad_ing = col2.text_input("Unidad de Compra (ej. kg, L, unidad)")
        precio_ing = col3.number_input("Precio por Unidad de Compra (€)", min_value=0.01, step=0.01)
        
        submitted = st.form_submit_button("Añadir/Actualizar Ingrediente")
        
        if submitted and nombre_ing and unidad_ing and precio_ing > 0:
            nuevo_ing = pd.DataFrame([{
                "Nombre": nombre_ing.strip().title(),
                "Unidad": unidad_ing.lower(),
                "Precio (€)": precio_ing
            }])
            
            if not df_biblioteca.empty:
                df_biblioteca = df_biblioteca[df_biblioteca["Nombre"] != nombre_ing.strip().title()]
            
            df_biblioteca = pd.concat([df_biblioteca, nuevo_ing], ignore_index=True)
            
            try:
                df_biblioteca.to_excel(FILE_BIBLIOTECA, index=False)
                st.success(f"¡Ingrediente '{nombre_ing}' guardado en la biblioteca!")
            except Exception as e:
                st.error(f"No se pudo guardar la biblioteca: {e}")

    if not df_biblioteca.empty:
        st.dataframe(df_biblioteca.sort_values("Nombre"), use_container_width=True)
    else:
        st.info("Tu biblioteca de ingredientes está vacía. Añade uno para empezar.")


    # --- PARTE 2: DEFINIR RECETA Y CALCULAR RENTABILIDAD ---
    st.markdown("---")
    st.subheader("2. 🍳 Definir Receta y Calcular Rentabilidad")
    
    if df_biblioteca.empty:
        st.warning("Debes añadir al menos un ingrediente a tu biblioteca (arriba) para poder definir una receta.")
    else:
        if 'Categoría' in df_ventas.columns:
            platos_menu = df_ventas[df_ventas['Categoría'].isin(['Plato', 'Postre'])]['Producto'].unique()
        else:
            platos_menu = df_ventas['Producto'].unique() 
            
        plato = st.selectbox("Selecciona un plato del menú de ventas:", sorted(platos_menu))

        if plato:
            precio_venta = df_ventas[df_ventas["Producto"] == plato]["Precio Unitario (€)"].mean()
            st.info(f"💵 Precio medio de venta de '{plato}': **{precio_venta:.2f} €**")

            num_ing_receta = st.number_input("Número de ingredientes en esta receta:", min_value=1, step=1, key=f"num_ing_{plato}")

            ingredientes_receta = []
            costo_total_plato = 0.0
            
            opciones_biblioteca = sorted(df_biblioteca["Nombre"].tolist())

            for i in range(int(num_ing_receta)):
                st.markdown(f"**Ingrediente #{i+1}**")
                col_rec1, col_rec2 = st.columns([2, 1])
                
                nombre_ing_receta = col_rec1.selectbox(
                    f"Selecciona ingrediente", 
                    options=[""] + opciones_biblioteca, 
                    key=f"sel{i}_{plato}"
                )
                
                if nombre_ing_receta:
                    ing_data = df_biblioteca[df_biblioteca["Nombre"] == nombre_ing_receta].iloc[0]
                    unidad_data = ing_data["Unidad"]
                    precio_data = ing_data["Precio (€)"]

                    cantidad_usada = col_rec2.number_input(
                        f"Cantidad usada (en '{unidad_data}')", 
                        min_value=0.0, 
                        step=0.01, 
                        key=f"cant{i}_{plato}"
                    )
                    
                    if cantidad_usada > 0:
                        costo_ing_receta = cantidad_usada * precio_data
                        costo_total_plato += costo_ing_receta
                        
                        ing_desc = f"{nombre_ing_receta} ({cantidad_usada} {unidad_data} @ {precio_data}€/{unidad_data} = {costo_ing_receta:.2f}€)"
                        ingredientes_receta.append(ing_desc)
                        col_rec1.caption(f"Costo: {costo_ing_receta:.2f} €")

            if st.button("Calcular y Guardar Rentabilidad"):
                if costo_total_plato > 0:
                    beneficio = precio_venta - costo_total_plato
                    margen = (beneficio / precio_venta) * 100 if precio_venta > 0 else 0

                    st.success(f"📈 Costo Total: {costo_total_plato:.2f} € | Beneficio: {beneficio:.2f} € | Margen: {margen:.1f}%")

                    registro = pd.DataFrame([{
                        "Plato": plato,
                        "Ingredientes": "; ".join(ingredientes_receta),
                        "Costo Ingredientes (€)": costo_total_plato,
                        "Precio Venta Medio (€)": precio_venta,
                        "Beneficio (€)": beneficio,
                        "Margen (%)": margen
                    }])

                    df_rent_existente = load_data(FILE_RENTABILIDAD) # <-- Usa la función simple de Excel
                    
                    if not df_rent_existente.empty:
                        df_rent_existente = df_rent_existente[df_rent_existente["Plato"] != plato]
                    
                    df_rent_final = pd.concat([df_rent_existente, registro], ignore_index=True)
                    
                    try:
                        df_rent_final.to_excel(FILE_RENTABILIDAD, index=False)
                        st.info(f"💾 Rentabilidad de '{plato}' guardada correctamente en `{FILE_RENTABILIDAD}`")
                        st.dataframe(df_rent_final.sort_values("Plato").tail(5), use_container_width=True)
                    except Exception as e:
                        st.error(f"No se pudo guardar el archivo de rentabilidad: {e}")
                else:
                    st.error("El costo total es 0. Asegúrate de añadir ingredientes y sus cantidades.")


# === 3️⃣ ANÁLISIS DE INGENIERÍA DE MENÚ (NUEVO) ===
elif opcion == "📈 Análisis de Menú":
    st.title("📈 Análisis de Ingeniería de Menú")
    st.info("""
    Este análisis clasifica tus platos en cuatro categorías para ayudarte a tomar decisiones estratégicas:
    - **⭐ Estrellas:** Alta popularidad y alta rentabilidad. ¡Tus ganadores!
    - **🧩 Puzzles:** Baja popularidad pero alta rentabilidad. ¿Cómo venderlos más?
    - **🐄 Vacas Lecheras (Cash Cows):** Alta popularidad pero baja rentabilidad. ¿Puedes reducir su costo?
    - **🐶 Perros (Dogs):** Baja popularidad y baja rentabilidad. Considera eliminarlos.
    """)

    # 1. Cargar datos de rentabilidad
    df_rent = load_data(FILE_RENTABILIDAD) # <-- Usa la función simple de Excel
    
    if df_rent.empty or "Plato" not in df_rent.columns or "Margen (%)" not in df_rent.columns:
        st.warning(f"No se encontró el archivo `{FILE_RENTABILIDAD}` o no tiene las columnas 'Plato' y 'Margen (%)'.")
        st.info("Por favor, calcula la rentabilidad de al menos dos platos en la sección '💰 Rentabilidad y Costos' para continuar.")
        st.stop()

    # 2. Cargar datos de popularidad (ventas)
    df_pop = df_ventas.groupby("Producto")["Cantidad"].sum().reset_index()
    df_pop.columns = ["Plato", "Popularidad"]

    # 3. Unir los datos
    df_menu = pd.merge(df_pop, df_rent[["Plato", "Margen (%)"]], on="Plato", how="inner")

    if len(df_menu) < 2:
        st.warning("Se necesitan datos de ventas y rentabilidad para al menos dos platos coincidentes para realizar el análisis.")
        st.stop()

    # 4. Calcular los promedios para definir los cuadrantes
    avg_pop = df_menu["Popularidad"].mean()
    avg_margen = df_menu["Margen (%)"].mean()

    # 5. Clasificar cada plato
    def classify_dish(row, avg_pop, avg_margen):
        if row["Popularidad"] >= avg_pop and row["Margen (%)"] >= avg_margen:
            return "⭐ Estrella (Star)"
        elif row["Popularidad"] < avg_pop and row["Margen (%)"] >= avg_margen:
            return "🧩 Puzzle"
        elif row["Popularidad"] >= avg_pop and row["Margen (%)"] < avg_margen:
            return "🐄 Vaca Lechera (Cash Cow)"
        else:
            return "🐶 Perro (Dog)"

    df_menu["Clasificación"] = df_menu.apply(lambda row: classify_dish(row, avg_pop, avg_margen), axis=1)

    # 6. Crear el Gráfico de Dispersión (Scatter Plot)
    st.subheader("📊 Matriz de Análisis de Menú")
    
    fig, ax = plt.subplots(figsize=(10, 6))

    colors = {
        "⭐ Estrella (Star)": "green",
        "🧩 Puzzle": "orange",
        "🐄 Vaca Lechera (Cash Cow)": "blue",
        "🐶 Perro (Dog)": "red"
    }

    # Dibujar los puntos
    for cat, color in colors.items():
        subset = df_menu[df_menu["Clasificación"] == cat]
        ax.scatter(subset["Popularidad"], subset["Margen (%)"], label=cat, color=color, s=120, alpha=0.7)

    # Añadir líneas de promedio
    ax.axhline(avg_margen, color='grey', linestyle='--')
    ax.axvline(avg_pop, color='grey', linestyle='--')

    # Añadir etiquetas a los puntos
    for i, row in df_menu.iterrows():
        ax.text(row["Popularidad"] + 0.5, row["Margen (%)"] + 0.5, row["Plato"], fontsize=9)

    # Añadir etiquetas de los cuadrantes
    ax.text(avg_pop * 1.01, avg_margen * 1.01, 'Estrellas', fontsize=12, color='green', weight='bold')
    ax.text(avg_pop * 0.99, avg_margen * 1.01, 'Puzzles', fontsize=12, color='orange', ha='right', weight='bold')
    ax.text(avg_pop * 1.01, avg_margen * 0.99, 'Vacas Lecheras', fontsize=12, color='blue', va='top', weight='bold')
    ax.text(avg_pop * 0.99, avg_margen * 0.99, 'Perros', fontsize=12, color='red', ha='right', va='top', weight='bold')

    ax.set_xlabel("Popularidad (Cantidad Vendida)")
    ax.set_ylabel("Rentabilidad (Margen %)")
    ax.set_title("Análisis de Ingeniería de Menú")
    ax.legend()
    ax.grid(True, linestyle=':', alpha=0.6)

    st.pyplot(fig)

    # 7. Mostrar Recomendaciones Accionables
    st.subheader("💡 Recomendaciones Accionables")
    
    for cat in colors.keys():
        st.markdown(f"---")
        st.markdown(f"### {cat}")
        
        platos_en_cat = df_menu[df_menu["Clasificación"] == cat]["Plato"].tolist()
        
        if not platos_en_cat:
            st.write("No hay platos en esta categoría.")
            continue

        st.write(f"**Platos:** {', '.join(platos_en_cat)}")
        
        if cat == "⭐ Estrella (Star)":
            st.success("**Acción:** ¡Sigue así! Mantén la calidad y dales visibilidad en el menú. Son tus productos ganadores.")
        elif cat == "🧩 Puzzle":
            st.warning("**Acción:** Tienen buen margen pero no se venden. Prueba a mejorar su descripción, cambiar su nombre, poner una foto en el menú o que los camareros los recomienden activamente.")
        elif cat == "🐄 Vaca Lechera (Cash Cow)":
            st.info("**Acción:** Son muy populares pero poco rentables. Revisa sus costos en la 'Biblioteca de Ingredientes' para ver si puedes reducirlos o considera un ligero aumento de precio que no afecte la demanda.")
        elif cat == "🐶 Perro (Dog)":
            st.error("**Acción:** Tienen baja popularidad y baja rentabilidad. Ocupan espacio y esfuerzo. Considera simplificar la receta para bajar costos drásticamente o eliminarlos del menú.")

    st.markdown("---")
    st.subheader("Datos del Análisis")
    st.dataframe(df_menu.set_index("Plato"), use_container_width=True)


# === 4️⃣ PREDICCIÓN DE DEMANDA (Mejorada) ===
elif opcion == "🤖 Predicción de Demanda":
    st.title("🤖 Predicción de Demanda (Próximos 7 días)")
    st.caption("Predicción basada en el modelo Prophet con estacionalidad diaria y semanal, usando datos históricos de ventas.")

    # --- PREDICCIÓN DE CANTIDAD (CLIENTELA/DEMANDA) ---
    st.subheader("👥 Predicción de Platos Vendidos (Demanda)")
    
    # Agrupar ventas por día (cantidad total de platos)
    ventas_diarias_cant = df_ventas.groupby(df_ventas['Fecha'].dt.date)["Cantidad"].sum().reset_index()
    ventas_diarias_cant["Fecha"] = pd.to_datetime(ventas_diarias_cant["Fecha"])
    ventas_diarias_cant = ventas_diarias_cant.sort_values("Fecha")

    if len(ventas_diarias_cant) > 2:
        df_prophet_cant = ventas_diarias_cant.rename(columns={"Fecha": "ds", "Cantidad": "y"})
        
        m_cant = Prophet(daily_seasonality=True, weekly_seasonality=True)
        m_cant.fit(df_prophet_cant)

        future_cant = m_cant.make_future_dataframe(periods=7, freq='D')
        forecast_cant = m_cant.predict(future_cant)

        df_pred_cant = forecast_cant[forecast_cant["ds"] > df_prophet_cant["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]
        df_pred_cant = df_pred_cant.rename(columns={"ds": "Fecha", "yhat": "Predicción Platos"})
        df_pred_cant["Predicción Platos"] = df_pred_cant["Predicción Platos"].apply(lambda x: max(round(x), 0))
        df_pred_cant["Fecha"] = df_pred_cant["Fecha"].dt.date
        
        st.dataframe(df_pred_cant.set_index("Fecha"), use_container_width=True)

        fig_cant, ax_cant = plt.subplots(figsize=(10, 5))
        m_cant.plot(forecast_cant, ax=ax_cant, xlabel="Fecha", ylabel="Platos Vendidos")
        ax_cant.set_title("Predicción de Platos Vendidos (7 días)")
        st.pyplot(fig_cant)

        promedio_esperado_cant = df_pred_cant["Predicción Platos"].mean()
        st.metric("📈 Promedio esperado diario (platos)", f"{int(promedio_esperado_cant)} platos/día")
    else:
        st.warning("No hay suficientes datos históricos (se necesitan > 2 días) para predecir la cantidad de platos.")


    # --- PREDICCIÓN DE VENTAS (€) ---
    st.markdown("---")
    st.subheader("💸 Predicción de Ventas (€)")

    ventas_diarias_eur = df_ventas.groupby(df_ventas['Fecha'].dt.date)["Total Venta (€)"].sum().reset_index()
    ventas_diarias_eur["Fecha"] = pd.to_datetime(ventas_diarias_eur["Fecha"])
    ventas_diarias_eur = ventas_diarias_eur.sort_values("Fecha")

    if len(ventas_diarias_eur) > 2:
        df_prophet_eur = ventas_diarias_eur.rename(columns={"Fecha": "ds", "Total Venta (€)": "y"})
        
        m_eur = Prophet(daily_seasonality=True, weekly_seasonality=True)
        m_eur.fit(df_prophet_eur)

        future_eur = m_eur.make_future_dataframe(periods=7, freq='D')
        forecast_eur = m_eur.predict(future_eur)

        df_pred_eur = forecast_eur[forecast_eur["ds"] > df_prophet_eur["ds"].max()][["ds", "yhat", "yhat_lower", "yhat_upper"]]
        df_pred_eur = df_pred_eur.rename(columns={"ds": "Fecha", "yhat": "Predicción Ventas (€)"})
        df_pred_eur["Predicción Ventas (€)"] = df_pred_eur["Predicción Ventas (€)"].apply(lambda x: max(round(x, 2), 0))
        df_pred_eur["Fecha"] = df_pred_eur["Fecha"].dt.date
        
        st.dataframe(df_pred_eur.set_index("Fecha"), use_container_width=True)

        fig_eur, ax_eur = plt.subplots(figsize=(10, 5))
        m_eur.plot(forecast_eur, ax=ax_eur, xlabel="Fecha", ylabel="Ventas (€)")
        ax_eur.set_title("Predicción de Ventas (€) (7 días)")
        st.pyplot(fig_eur)

        promedio_esperado_eur = df_pred_eur["Predicción Ventas (€)"].mean()
        st.metric("📈 Promedio esperado diario (ventas)", f"{promedio_esperado_eur:,.2f} €/día")
    else:
        st.warning("No hay suficientes datos históricos (se necesitan > 2 días) para predecir las ventas.")