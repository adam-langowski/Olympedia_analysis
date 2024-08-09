import streamlit as st  
import matplotlib.pyplot as plt  
import pandas as pd  
import folium  
from folium.plugins import HeatMap  
from streamlit_folium import st_folium  
import geopandas as gpd  


# LOAD DATA  
nocs = pd.read_csv("clean-data/noc_regions.csv")  
nocs = nocs.sort_values('region', ascending=True)  
region_to_noc = dict(zip(nocs['NOC'], nocs['region']))

results_df = pd.read_csv("clean-data/results.csv", sep=',')  
medals_counts = results_df[results_df["medal"].notna()]    

# UI  
st.title("Olympics Stats Preview")  
st.sidebar.title("Filters")  
selected_countries = st.sidebar.multiselect("Select countries", options=list(region_to_noc.keys()),
                                            default=['POL']) 

include_winter = st.sidebar.checkbox("Include winter games?", True)  

# HELPERS  
def load_bios_data():  
    bios = pd.read_csv('clean-data/bios_locs.csv')  
    return bios  

def load_results_data():  
    results = pd.read_csv('clean-data/results.csv')  
    return results  


# DATA   
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
    medals = results[(results['medal'].notna()) & (~results['event'].str.endswith('(YOG)'))]  
    medals_filtered = medals.drop_duplicates(['year', 'type', 'discipline', 'noc', 'event', 'medal'])  
    medals_by_year = medals_filtered.groupby(['noc', 'year'])['medal'].count().reset_index()  
    return medals_by_year  

def get_world_map():
    models_filtered_team = medals_counts.drop_duplicates(["year", "type", "discipline", "noc", "event", "medal"])  

    models_filtered_youth = models_filtered_team[~models_filtered_team["event"].str.endswith('YOG')]  
    models_filtered_youth.groupby(["noc"])["medal"].value_counts()  
    pivot_table = models_filtered_youth.pivot_table(index="noc", columns="medal", aggfunc="size", fill_value=0)  
    data = pivot_table.reset_index()  

    world = gpd.read_file("countries_map/ne_110m_admin_0_countries.shp")  
                                        
    data = pivot_table.reset_index()

    world = world.merge(data, how="left", left_on="ISO_A3", right_on="noc") 

    data['Total'] = data['Gold'] + data['Silver'] + data['Bronze']
    world = world.merge(data, how="left", left_on="ISO_A3", right_on="noc")

    world["Total"] = world["Total"].fillna(0)

    st.subheader("Total Medals Count by Country")  

    fig, ax = plt.subplots(1, 1, figsize=(15, 10))  
    world.boundary.plot(ax=ax, linewidth=1)  
    world.plot(column="Total", ax=ax, legend=True,  
            legend_kwds={'label': "TOTAL MEDALS COUNT",  
                            'orientation': "horizontal"},  
            cmap='YlGnBu')  

    plt.title("Total medals count by country")  
    st.pyplot(fig)  

# LEADERBOARDS 
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


# TABS  
tab1, tab2, tab3 = st.tabs(["Medals per country", "Heatmap of Athletes", "Leaderboards"])  

# MEDALS PER COUNTRY TAB  
with tab1:  
    st.subheader("Medals by Year")  
    medals = get_medals(selected_countries)  
    fig, ax = plt.subplots(figsize=(10, 7))  
    for country in selected_countries:  
        country_medals = medals[medals['noc'] == country]  
        ax.plot(country_medals['year'], country_medals['medal'], label=region_to_noc[country])  
    ax.set_xlabel('Year')  
    ax.set_ylabel('Medal Count')  
    ax.set_title('Medals by Year for Selected Countries')  
    ax.legend()   
    st.pyplot(fig)  

    get_world_map()

# HEATMAP TAB  
with tab2:  
    st.subheader("Heatmap of Athletes")  
    bios = bios_df(selected_countries)  
    if not bios.empty:  
        m = folium.Map(location=[bios['lat'].mean(), bios['long'].mean()], zoom_start=2)  
        heat_data = [[row['lat'], row['long']] for index, row in bios.iterrows()]  
        HeatMap(heat_data).add_to(m)  
        st_folium(m, width=1200, height=700)  
    else:  
        st.write("No data available for the selected countries.")  
        
# LEADERBOARDS TAB  
with tab3:
    st.subheader("Top 50 Athletes by Medal Count")
    
    sort_by = st.selectbox("Sort by:", ["Total Medals", "Gold Medals"])
    
    leaderboard = get_leaderboard(selected_countries, sort_by)
    st.table(leaderboard)