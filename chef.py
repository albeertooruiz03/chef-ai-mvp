import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from prophet import Prophet
# Importamos la conexión oficial de Streamlit a Google Sheets
from streamlit_gsheets import GSheetsConnection

# === CONFIGURACIÓN DE LA PÁGINA ===
st.set_page_config(
    page_title="Chef.AI Dashboard",
    page_icon="🍽️",
    layout="wide"
)

# === URL DE TU GOOGLE SHEET (¡Cámbiala por la tuya!) ===
SHEET_URL = "https://docs.google.com/spreadsheets/d/1sKwhKO46r6ZRUO70GB8afjY_YYvQH7VzES4bCN3AhEY/edit?gid=1651162993#gid=1651162993"

# Crear la conexión global a Google Sheets
# Se conecta usando los "Secrets" que configuraste en Streamlit Cloud
conn = st.connection("gsheets", type=GSheetsConnection)


# === NUEVAS FUNCIONES PARA CARGAR DATOS DESDE GOOGLE SHEETS ===

@st.cache_data(ttl=600) # Cachea los datos por 10 minutos para no saturar a Google
def load_sheet_data(worksheet_name):
    """Carga una pestaña específica del Google Sheet y devuelve un DataFrame"""
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name)
        # Limpiar filas completamente vacías
        df = df.dropna(how='all')
        return df
    except Exception as e:
        st.error(f"Error al conectar con la pestaña '{worksheet_name}': {e}")
        return pd.DataFrame()

def save_to_sheet(df, worksheet_name):
    """Sobreescribe una pestaña específica del Google Sheet con el DataFrame nuevo"""
    try:
        # Primero leemos para asegurarnos de que no perdemos estructura, luego limpiamos y guardamos
        conn.update(worksheet=worksheet_name, data=df, spreadsheet=SHEET_URL)
        # Limpiamos el caché para que la app lea los datos frescos en el próximo click
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Error al guardar en la pestaña '{worksheet_name}': {e}")
        return False

# === CARGAR DATOS PRINCIPALES ===
# Cargamos desde las pestañas (asegúrate de que los nombres coinciden en tu Google Sheet)
df_ventas = load_sheet_data("Ventas")
df_rentabilidad = load_sheet_data("Rentabilidad")
df_biblioteca = load_sheet_data("Biblioteca")

# Preprocesamiento de Ventas (si hay datos)
if not df_ventas.empty and 'Fecha' in df_ventas.columns:
    df_ventas['Fecha'] = pd.to_datetime(df_ventas['Fecha'], errors='coerce')
    df_ventas = df_ventas.dropna(subset=['Fecha'])

if df_ventas.empty:
    st.warning("⚠️ No hay datos en la pestaña 'Ventas' de Google Sheets. Añade algunos datos para poder ver el dashboard.")
    st.stop()


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
    ventas_por_dia = df_ventas.groupby(df_ventas['Fecha'].dt.date)["Total Venta (€)"].sum()

    col1, col2 = st.columns(2)
    col1.metric("💰 Total de Ventas", f"{total_ventas:,.2f} €")
    col2.metric("🍽️ Nº Total de Platos Vendidos", int(total_platos))

    st.subheader("🥇 Platos más vendidos (Top 5)")
    st.bar_chart(platos_mas_vendidos)

    st.subheader("📆 Evolución de Ventas por Día")
    st.line_chart(ventas_por_dia)

    st.markdown("---")
    st.subheader("💰 Resumen de Rentabilidad por Plato")

    # Usamos el dataframe que ya cargamos desde Google Sheets al principio
    df_rent = df_rentabilidad

    if not df_rent.empty:
        columnas_rent = ["Plato", "Costo Ingredientes (€)", "Precio Venta Medio (€)", "Beneficio (€)", "Margen (%)"]
        if all(col in df_rent.columns for col in columnas_rent):
            st.dataframe(df_rent[columnas_rent], use_container_width=True)

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
            st.warning("La pestaña 'Rentabilidad' en Google Sheets no tiene las columnas esperadas.")
            st.dataframe(df_rent)
    else:
        st.info("Aún no se ha calculado la rentabilidad de ningún plato. Ve a la sección '💰 Rentabilidad y Costos'.")


# === 2️⃣ CALCULADORA DE RENTABILIDAD ===
elif opcion == "💰 Rentabilidad y Costos":
    st.title("💰 Gestión de Costos y Rentabilidad")
    st.info("Sigue los pasos: 1. Añade ingredientes a tu biblioteca. 2. Define la receta de un plato y calcula su rentabilidad.")

    st.markdown("---")
    st.subheader("1. 📚 Biblioteca de Ingredientes")
    
    # Usamos el dataframe ya cargado
    df_bib = df_biblioteca

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
            
            if not df_bib.empty:
                # Actualiza si existe, o añade si es nuevo
                df_bib = df_bib[df_bib["Nombre"] != nombre_ing.strip().title()]
            
            df_bib_final = pd.concat([df_bib, nuevo_ing], ignore_index=True)
            
            # ¡Guardamos en Google Sheets!
            if save_to_sheet(df_bib_final, "Biblioteca"):
                st.success(f"¡Ingrediente '{nombre_ing}' guardado en la nube!")
                st.experimental_rerun() # Recarga la app para mostrar el nuevo ingrediente

    if not df_bib.empty:
        st.dataframe(df_bib.sort_values("Nombre"), use_container_width=True)
    else:
        st.info("Tu biblioteca de ingredientes está vacía. Añade uno para empezar.")

    st.markdown("---")
    st.subheader("2. 🍳 Definir Receta y Calcular Rentabilidad")
    
    if df_bib.empty:
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
            
            opciones_biblioteca = sorted(df_bib["Nombre"].tolist())

            for i in range(int(num_ing_receta)):
                st.markdown(f"**Ingrediente #{i+1}**")
                col_rec1, col_rec2 = st.columns([2, 1])
                
                nombre_ing_receta = col_rec1.selectbox(
                    f"Selecciona ingrediente", 
                    options=[""] + opciones_biblioteca, 
                    key=f"sel{i}_{plato}"
                )
                
                if nombre_ing_receta:
                    ing_data = df_bib[df_bib["Nombre"] == nombre_ing_receta].iloc[0]
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

                    df_rent_existente = df_rentabilidad
                    
                    if not df_rent_existente.empty:
                        df_rent_existente = df_rent_existente[df_rent_existente["Plato"] != plato]
                    
                    df_rent_final = pd.concat([df_rent_existente, registro], ignore_index=True)
                    
                    # ¡Guardamos en Google Sheets!
                    if save_to_sheet(df_rent_final, "Rentabilidad"):
                        st.info(f"💾 Rentabilidad de '{plato}' guardada en la nube.")
                        st.dataframe(df_rent_final.sort_values("Plato").tail(5), use_container_width=True)
                else:
                    st.error("El costo total es 0. Asegúrate de añadir ingredientes y cantidades.")


# === 3️⃣ ANÁLISIS DE INGENIERÍA DE MENÚ ===
elif opcion == "📈 Análisis de Menú":
    st.title("📈 Análisis de Ingeniería de Menú")
    
    df_rent = df_rentabilidad
    
    if df_rent.empty or "Plato" not in df_rent.columns or "Margen (%)" not in df_rent.columns:
        st.warning("Aún no hay datos suficientes de rentabilidad en Google Sheets.")
        st.stop()

    df_pop = df_ventas.groupby("Producto")["Cantidad"].sum().reset_index()
    df_pop.columns = ["Plato", "Popularidad"]

    df_menu = pd.merge(df_pop, df_rent[["Plato", "Margen (%)"]], on="Plato", how="inner")

    if len(df_menu) < 2:
        st.warning("Calcula la rentabilidad de al menos dos platos para ver el gráfico de matriz.")
        st.stop()

    avg_pop = df_menu["Popularidad"].mean()
    avg_margen = df_menu["Margen (%)"].mean()

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

    st.subheader("📊 Matriz de Análisis de Menú")
    fig, ax = plt.subplots(figsize=(10, 6))

    colors = {"⭐ Estrella (Star)": "green", "🧩 Puzzle": "orange", "🐄 Vaca Lechera (Cash Cow)": "blue", "🐶 Perro (Dog)": "red"}
    
    # Fijar el color del texto a blanco para que se lea en el modo oscuro
    plt.rcParams['text.color'] = 'white'
    plt.rcParams['axes.labelcolor'] = 'white'
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    fig.patch.set_facecolor('#1E2329') # Fondo acorde al modo oscuro
    ax.set_facecolor('#1E2329')

    for cat, color in colors.items():
        subset = df_menu[df_menu["Clasificación"] == cat]
        ax.scatter(subset["Popularidad"], subset["Margen (%)"], label=cat, color=color, s=120, alpha=0.7)

    ax.axhline(avg_margen, color='grey', linestyle='--')
    ax.axvline(avg_pop, color='grey', linestyle='--')

    for i, row in df_menu.iterrows():
        ax.text(row["Popularidad"] + 0.5, row["Margen (%)"] + 0.5, row["Plato"], fontsize=9, color='white')

    ax.set_xlabel("Popularidad (Cantidad Vendida)")
    ax.set_ylabel("Rentabilidad (Margen %)")
    ax.legend()
    st.pyplot(fig)


# === 4️⃣ PREDICCIÓN DE DEMANDA ===
elif opcion == "🤖 Predicción de Demanda":
    st.title("🤖 Predicción de Demanda (Próximos 7 días)")
    
    st.subheader("👥 Predicción de Platos Vendidos (Demanda)")
    
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
        
        fig_cant = m_cant.plot(forecast_cant, xlabel="Fecha", ylabel="Platos Vendidos")
        st.pyplot(fig_cant)

        promedio_esperado_cant = df_pred_cant["Predicción Platos"].mean()
        st.metric("📈 Promedio esperado diario (platos)", f"{int(promedio_esperado_cant)} platos/día")
    else:
        st.warning("No hay suficientes datos históricos en la hoja de Google Sheets (se necesitan > 2 días).")
