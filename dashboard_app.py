import streamlit as st  
import matplotlib.pyplot as plt  
import pandas as pd  
import folium  
from folium.plugins import HeatMap  
from streamlit_folium import st_folium  
import geopandas as gpd  
import seaborn as sns

# UI
st.set_page_config(
    page_title="Olympics Stats",
    initial_sidebar_state="expanded"
)
sns.set_style("whitegrid")
plt.style.use('seaborn-poster')
st.title("🏅 Olympics Stats Dashboard")  
st.sidebar.title("Filters")  

# DATA  
nocs = pd.read_csv("clean-data/noc_regions.csv")  
nocs = nocs.sort_values('region', ascending=True)  
region_to_noc = dict(zip(nocs['NOC'], nocs['region']))

results_df = pd.read_csv("clean-data/results.csv", sep=',')  
medals_counts = results_df[results_df["medal"].notna()]    

# FILTERS
selected_countries = st.sidebar.multiselect("Select countries", options=list(region_to_noc.keys()),
                                            default=['POL']) 

include_winter = st.sidebar.checkbox("Include Winter Games?", True)  


# Load Data Helpers  
def load_bios_data():  
    bios = pd.read_csv('clean-data/bios_locs.csv')  
    return bios  

def load_results_data():  
    results = pd.read_csv('clean-data/results.csv')
    results = results[(~results['event'].str.endswith('(YOG)'))]    
    return results  


# Data Processing   
def bios_df(selected_country):  
    bios = load_bios_data()  
    bios = bios[bios['born_country'].isin(selected_country)] 

    country_df = bios[(bios['lat'].notna()) & (bios['long'].notna())]  
    return country_df  

def results_df(selected_country):  
    df = load_results_data()  
    df = df[df['noc'].isin(selected_country)]   
    if not include_winter:  
        df = df[df['type'] == 'Summer']  
    return df  

def get_medals(selected_country):  
    results = results_df(selected_country)  
    medals = results[(results['medal'].notna())]  
    medals_filtered = medals.drop_duplicates(['year', 'type', 'discipline', 'noc', 'event', 'medal'])  
    medals_by_year = medals_filtered.groupby(['noc', 'year'])['medal'].count().reset_index()  
    return medals_by_year  

def get_world_map():
    models_filtered_team = medals_counts.drop_duplicates(["year", "type", "discipline", "noc", "event", "medal"])  
    models_filtered_team.groupby(["noc"])["medal"].value_counts()  
    pivot_table = models_filtered_team.pivot_table(index="noc", columns="medal", aggfunc="size", fill_value=0)  
    data = pivot_table.reset_index()  

    world = gpd.read_file("countries_map/ne_110m_admin_0_countries.shp")  
    data = pivot_table.reset_index()
    world = world.merge(data, how="left", left_on="ISO_A3", right_on="noc") 
    data['Total'] = data['Gold'] + data['Silver'] + data['Bronze']
    world = world.merge(data, how="left", left_on="ISO_A3", right_on="noc")
    world["Total"] = world["Total"].fillna(0)

    st.subheader("🌍 Total Medals Count by Country")  

    fig, ax = plt.subplots(1, 1, figsize=(15, 10))  
    world.boundary.plot(ax=ax, linewidth=1, color='black')  
    world.plot(column="Total", ax=ax, legend=True,  
            legend_kwds={'label': "Total Medals Count",  
                            'orientation': "horizontal"},  
            cmap='YlGnBu')  

    plt.title("Total Medals Count by Country", fontsize=16)  
    st.pyplot(fig)  

# Leaderboards 
def get_leaderboard(selected_country, sort_by):
    results = results_df(selected_country)
    bios = load_bios_data()

    medalists = results[results['medal'].notna()]

    leaderboard = medalists.groupby(['athlete_id', 'medal']).size().unstack(fill_value=0)
    
    for medal_type in ['Gold', 'Silver', 'Bronze']:
        if medal_type not in leaderboard.columns:
            leaderboard[medal_type] = 0
    
    leaderboard = leaderboard.merge(bios[['athlete_id', 'name']], on='athlete_id')

    leaderboard['Total Medals'] = leaderboard['Gold'] + leaderboard['Silver'] + leaderboard['Bronze']

    # Sort option
    if sort_by == 'Gold Medals':
        leaderboard = leaderboard.sort_values(by=['Gold', 'Silver', 'Bronze'], ascending=False)
    else:  
        leaderboard = leaderboard.sort_values(by='Total Medals', ascending=False)

    leaderboard = leaderboard.head(50)

    return leaderboard[['name', 'Gold', 'Silver', 'Bronze']]


# Biometrics 
def get_biometrics(selected_country):
    bios = load_bios_data()
    results = results_df(selected_country)

    merged_df = results.merge(bios, on='athlete_id')

    filtered_df = merged_df[(merged_df['height_cm'].notna()) & (merged_df['weight_kg'].notna())]

    biometrics_by_year = filtered_df.groupby('year')[['height_cm', 'weight_kg']].mean().reset_index()

    filtered_df['born_date'] = pd.to_datetime(filtered_df['born_date'], errors='coerce')
    filtered_df['age'] = filtered_df['year'] - filtered_df['born_date'].dt.year

    age_by_year = filtered_df.groupby('year')['age'].mean().reset_index()

    return biometrics_by_year, age_by_year


# Tabs  
tab1, tab2, tab3, tab4 = st.tabs(["🏅 Medals per Country", "📍 Heatmap of Athletes", "🏆 Leaderboards", "📊 Biometrics"])  

# Medals per Country Tab  
with tab1:  
    st.subheader("📈 Medals by Year")  
    medals = get_medals(selected_countries)  
    fig, ax = plt.subplots(figsize=(10, 7))  
    for country in selected_countries:  
        country_medals = medals[medals['noc'] == country]  
        ax.plot(country_medals['year'], country_medals['medal'], label=region_to_noc[country], linewidth=2)  
    ax.set_xlabel('Year', fontsize=14)  
    ax.set_ylabel('Medal Count', fontsize=14)  
    ax.set_title('Medals by Year for Selected Countries', fontsize=16)  
    ax.legend(title="Country")  
    st.pyplot(fig)  

    get_world_map()

# Heatmap Tab  
with tab2:  
    st.subheader("📍 Heatmap of Athletes")  
    bios = bios_df(selected_countries)  
    if not bios.empty:  
        m = folium.Map(location=[bios['lat'].mean(), bios['long'].mean()], zoom_start=2, tiles='CartoDB positron')  
        heat_data = [[row['lat'], row['long']] for index, row in bios.iterrows()]  
        HeatMap(heat_data, radius=15).add_to(m)  
        st_folium(m, width=1200, height=700)  
    else:  
        st.write("No data available for the selected countries.")  
        
# Leaderboards Tab  
with tab3:
    st.subheader("🏆 Top 50 Athletes by Medal Count")
    
    sort_by = st.selectbox("Sort by:", ["Total Medals", "Gold Medals"])
    
    leaderboard = get_leaderboard(selected_countries, sort_by)
    st.table(leaderboard.style.set_table_styles([
        {'selector': 'thead th', 'props': [('background-color', '#4CAF50'), ('color', 'white'), ('font-weight', 'bold')]},
        {'selector': 'tbody td', 'props': [('font-size', '14px')]}
    ]))
    
# Biometrics Tab
with tab4:
    st.subheader("📊 Average Height, Weight and Age of Olympic Athletes")
    
    biometrics, age_by_year = get_biometrics(selected_countries)
    
    fig, ax1 = plt.subplots(figsize=(10, 7))

    ax1.set_xlabel('Year', fontsize=14)
    ax1.set_ylabel('Average Height (cm)', color='tab:blue', fontsize=14)
    ax1.plot(biometrics['year'], biometrics['height_cm'], color='tab:blue', label='Height (cm)', linewidth=2)
    ax1.tick_params(axis='y', labelcolor='tab:blue')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Average Weight (kg)', color='tab:orange', fontsize=14)
    ax2.plot(biometrics['year'], biometrics['weight_kg'], color='tab:orange', label='Weight (kg)', linewidth=2)
    ax2.tick_params(axis='y', labelcolor='tab:orange')
    ax1.set_title('Average Height & Weight of Athletes Over the Years', fontsize=16)

    fig.tight_layout()
    st.pyplot(fig)

    st.subheader("📅 Average Age Over the Years")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.plot(age_by_year['year'], age_by_year['age'], color='tab:green', marker='o', linewidth=2)
    ax.set_xlabel('Year', fontsize=14)
    ax.set_ylabel('Average Age', fontsize=14)
    ax.set_title('Average Age of Athletes Over the Years', fontsize=16)
    st.pyplot(fig)