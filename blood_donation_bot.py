import requests # HTTP connection
import pandas as pd # data manipulation
import pyarrow.parquet as pq 
from datetime import datetime


import matplotlib.pyplot as plt # plotting library
import matplotlib.cm as cm # colormap for mapping numerical values to color for visual
import seaborn as sns
import numpy as np 
from numpy.polynomial.polynomial import Polynomial # Used in creating trendline for plotting

# Necessary for building and running telegram bot
from bob_telegram_tools.bot import TelegramBot
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application, MessageHandler, filters

BOT_TOKEN = '???????'
BOT_USERNAME = '@alifnrzm_bot'

# Data Ingestion
def load_data(csv_urls = [], parquet_url=None):

    donations_by_facility_df = None
    donations_by_state_df = None
    new_donors_facility_df = None 
    new_donors_state_df = None
    regular_donor_df = None

    # List of URL tuples pointing to csv and corresponding name for DF
    csv_urls = [
        ("https://raw.githubusercontent.com/MoH-Malaysia/data-darah-public/main/donations_facility.csv", "donate_facility"),
        ("https://raw.githubusercontent.com/MoH-Malaysia/data-darah-public/main/donations_state.csv", "donate_state"),
        ("https://raw.githubusercontent.com/MoH-Malaysia/data-darah-public/main/newdonors_facility.csv", "age_facility"),
        ("https://raw.githubusercontent.com/MoH-Malaysia/data-darah-public/main/newdonors_state.csv", "age_state")
    ]

    # URL pointing to Parquet file
    parquet_url = "https://dub.sh/ds-data-granular"

    # Load CSV files
    for url, df_name in csv_urls:
        if df_name == "donate_facility":
            donations_by_facility_df = pd.read_csv(url)
        elif df_name == "donate_state":
            donations_by_state_df = pd.read_csv(url)
        elif df_name == "age_facility":
            new_donors_facility_df = pd.read_csv(url)
        elif df_name == "age_state":
            new_donors_state_df = pd.read_csv(url)

    # Load Parquet file
    regular_donor_df = pd.read_parquet(parquet_url)

    return (donations_by_facility_df, 
            donations_by_state_df,
            new_donors_facility_df,
            new_donors_state_df,
            regular_donor_df)

donations_by_facility_df, donations_by_state_df, new_donors_facility_df, new_donors_state_df, regular_donor_df = load_data()

# Data cleaning
def clean_data(dfs, date_col='date'):
    donations_by_facility_df, donations_by_state_df, new_donors_facility_df, new_donors_state_df, regular_donor_df = dfs

    for df in [donations_by_facility_df, donations_by_state_df, new_donors_facility_df, new_donors_state_df]:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
            df['year'] = df[date_col].dt.year

    regular_donor_df['visit_date'] = pd.to_datetime(regular_donor_df['visit_date'])
    regular_donor_df['birth_date'] = pd.to_datetime(regular_donor_df['birth_date']).dt.year
    regular_donor_df['year'] = regular_donor_df['visit_date'].dt.year
    return donations_by_facility_df, donations_by_state_df, new_donors_facility_df, new_donors_state_df, regular_donor_df


dfs = load_data()

dfs = clean_data(dfs)


# Transformatio and plot
def malaysia_trend_per_year():

    total_per_year = dfs[1].groupby(['state', 'year'])['daily'].sum().reset_index()

    state_data = total_per_year[total_per_year['state'] == 'Malaysia']

    bars = plt.bar(state_data['year'], state_data['daily'], color='tab:blue', label='Malaysia')

    z = np.polyfit(state_data['year'], state_data['daily'], 1)
    p = np.poly1d(z)

    plt.plot(state_data['year'], p(state_data['year']), color='tab:red', linestyle='--', label='Trendline')

    plt.title(f'Total Number of Blood Donations Per Year - Malaysia')
    plt.xlabel('Year')
    plt.ylabel('Total Donations')

    plt.xticks(state_data['year'], rotation=45)

    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig('mytrend.png')

def donor_retention():
    
    donation_freq = dfs[4].groupby(['year', 'donor_id']).size().reset_index(name='donation_count')
    regular_donors = donation_freq[donation_freq['donation_count'] >= 3]

    percentage_regular_donors_per_year = (
        donation_freq[donation_freq['donor_id'].isin(regular_donors['donor_id'])]
        .groupby('year')['donor_id']
        .nunique() / donation_freq.groupby('year')['donor_id'].nunique() * 100
    )

    
    plt.figure(figsize=(10, 6))
    plt.plot(percentage_regular_donors_per_year.index, percentage_regular_donors_per_year.values, marker='o', linestyle='-')


    for year, percentage in zip(percentage_regular_donors_per_year.index, percentage_regular_donors_per_year.values):
        plt.text(year, percentage, f'{percentage:.2f}%', ha='center', va='bottom')

    plt.title('Percentage of Regular Donors Over Total Donors (2012-2024)')
    plt.xlabel('Year')
    plt.ylabel('Percentage of Regular Donors')

    plt.tick_params(axis='y', which='both', left=False, right=False, labelleft=False)
    plt.savefig('regtrend.png')

def percentage_per_state():
    
    state_total = dfs[1].groupby('state')['daily'].sum().reset_index()

    state_total = state_total[state_total['state'] != 'Malaysia']

    state_total['total all'] = state_total['daily'].sum() 

    state_total['percentage'] = (state_total['daily'] / state_total['total all']) * 100

    state_total = state_total.sort_values(by='percentage', ascending=True).reset_index()
    
    plt.figure(figsize=(10, 6))
    colormap = cm.viridis
    
    bars = plt.barh(state_total['state'], state_total['percentage'], color=[colormap(i / len(state_total)) for i in range(len(state_total))])

    
    for bar, percentage in zip(bars, state_total['percentage']):
        plt.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2, f'{percentage:.2f}%', ha='left', va='center')

    plt.ylabel('State')
    plt.title('% Total Donations per State from 2006 to 2024')
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    plt.tick_params(axis='x', which='both', bottom=False, top=False, labelbottom=False)
    plt.savefig('statetrend.png')

def percentage_per_hospital():
    
    hospitals_states = {
    'Hospital Duchess Of Kent': 'Sabah',
    'Hospital Melaka': 'Melaka',
    'Hospital Miri': 'Sarawak',
    'Hospital Pulau Pinang': 'Pulau Pinang',
    'Hospital Queen Elizabeth II': 'Sabah',
    'Hospital Raja Perempuan Zainab II': 'Kelantan',
    'Hospital Raja Permaisuri Bainun': 'Perak',
    'Hospital Seberang Jaya': 'Pulau Pinang',
    'Hospital Seri Manjung': 'Perak',
    'Hospital Sibu': 'Sarawak',
    'Hospital Sultan Haji Ahmad Shah': 'Pahang',
    'Hospital Sultanah Aminah': 'Johor',
    'Hospital Sultanah Bahiyah': 'Kedah',
    'Hospital Sultanah Nora Ismail': 'Johor',
    'Hospital Sultanah Nur Zahirah': 'Terengganu',
    'Hospital Taiping': 'Perak',
    'Hospital Tawau': 'Sabah',
    'Hospital Tengku Ampuan Afzan': 'Pahang',
    'Hospital Tengku Ampuan Rahimah': 'Selangor',
    'Hospital Tuanku Jaafar': 'Negeri Sembilan',
    'Hospital Umum Sarawak': 'Sarawak',
    'Pusat Darah Negara': 'W.P. Kuala Lumpur'}

    dfs[0]['state'] = dfs[0]['hospital'].map(hospitals_states)

    hospital_total = dfs[0].groupby(['hospital','state'])['daily'].sum().reset_index()

    hospital_total['total all'] = hospital_total['daily'].sum()

    hospital_total['percentage'] = (hospital_total['daily']/hospital_total['total all']) * 100
    hospital_total = hospital_total.sort_values(by='percentage', ascending = True)

    state_colors = {
        'Sabah': 'blue',
        'Melaka': 'orange',
        'Sarawak': 'green',
        'Pulau Pinang': 'red',
        'Kelantan': 'purple',
        'Perak': 'brown',
        'Pahang': 'pink',
        'Johor': 'gray',
        'Kedah': 'olive',
        'Terengganu': 'cyan',
        'Selangor': 'yellow',
        'Negeri Sembilan': 'maroon',
        'W.P. Kuala Lumpur': 'navy'}


    colormap = {}
    for h, s in zip(hospital_total['hospital'], hospital_total['state']):
        colormap[h] = state_colors[s]
 
    plt.rcParams.update({'font.size': 10})
    fig, ax = plt.subplots()
    fig.set_size_inches(10, 8)
    bars = ax.barh(hospital_total['hospital'], hospital_total['percentage'], 
                   color=colormap.values())

    for bar, percentage in zip(bars, hospital_total['percentage']):
        plt.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                 f'{percentage:.2f}%', ha='left', va='center')

    handles = [plt.Rectangle((0,0),1,1, color=state_colors[s]) for s in state_colors]
    ax.legend(handles, state_colors.keys())

    fig.tight_layout()
    ax.set_ylabel('Hospital')
    ax.set_xlabel('Percentage')
    ax.set_title('Donations per Hospital')
    ax.grid(axis='x')
    plt.savefig('hospitaltrend.png')

def new_age_group_trend():

    my_age_group = dfs[3][dfs[3]['state'] == 'Malaysia']
    melted_age_group = pd.melt(my_age_group, id_vars=['date','year'], value_vars=['17-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60-64', 'other'])
    grouped_melted_age = melted_age_group.groupby(['variable','year'])['value'].sum().reset_index()
    plt.figure(figsize=(12,6))
    sns.lineplot(x='year', y='value', hue='variable', data=grouped_melted_age, marker='o')

    plt.title('New Donors Trends by Age Group (2006-2024)')
    plt.xlabel('Year')
    plt.ylabel('Number of Donations')
    plt.legend(title='Age Group', bbox_to_anchor=(1.05,1), loc='upper left')

    plt.xticks(ticks=grouped_melted_age['year'].unique(), rotation=45)
    plt.tight_layout()
    plt.savefig('newdonors.png')



# Commands
async def mytrend(update, context):
    
    malaysia_trend_per_year()
    plt.close()
    last_updated_date = dfs[1]['date'].max().strftime("%Y-%m-%d")
    message = f"Malaysia trend data updated at: {last_updated_date}"
    reason =  f"This graph shows the trend of blood donation number from 2006 until latest 2024 with added trendline to see increase in donation"
    await context.bot.send_photo(chat_id=update.message.chat_id, photo=open("mytrend.png", "rb"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=message)
    await context.bot.send_message(chat_id=update.message.chat_id, text=reason)

async def regtrend(update, context):
    donor_retention()
    plt.close()
    last_updated_date = dfs[4]['visit_date'].max().strftime("%Y-%m-%d")
    message = f"Regular donor trend data updated at: {last_updated_date}"
    reason = f"This graph is showing regular donors trend among registered donors from 2012 to latest 2024. Assuming that 3 or more is considered as regular donation"
    await context.bot.send_photo(chat_id=update.message.chat_id, photo=open("regtrend.png", "rb"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=message)
    await context.bot.send_message(chat_id=update.message.chat_id, text=reason)

async def statetrend(update, context):
    
    percentage_per_state()
    plt.close()
    last_updated_date = dfs[1]['date'].max().strftime("%Y-%m-%d")
    message = f"State trend data updated at: {last_updated_date}"
    reason = f"This graphs represents the % of donation per state from 2006 until latest 2024 with highest donors on top"
    await context.bot.send_photo(chat_id=update.message.chat_id, photo=open("statetrend.png", "rb"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=message)
    await context.bot.send_message(chat_id=update.message.chat_id, text=reason)

async def hospitaltrend(update, context):
    
    percentage_per_hospital()
    plt.close()
    last_updated_date = dfs[0]['date'].max().strftime("%Y-%m-%d")
    message = f"Hospital trend data updated at: {last_updated_date}"
    reason = f"This graphs represents the % of donation per hospital from 2006 until latest 2024 with highest donors on top"
    await context.bot.send_photo(chat_id=update.message.chat_id, photo=open("hospitaltrend.png", "rb"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=message)
    await context.bot.send_message(chat_id=update.message.chat_id, text=reason)

async def agetrend(update, context):

    new_age_group_trend()
    plt.close()
    last_updated_date = dfs[3]['date'].max().strftime("%Y-%m-%d")
    message = f"New donors age group data updated at: {last_updated_date}"
    reason = f"This graph represents the total donation of new donors in age group from 2006 until latest 2024"
    await context.bot.send_photo(chat_id=update.message.chat_id, photo=open("newdonors.png", "rb"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=message)
    await context.bot.send_message(chat_id=update.message.chat_id, text=reason)

async def startcommand(update, context):

    message = f"Hi, as of right now I only take 5 commands where you can find by typing / in the chat box. These 5 commands are the output of finding the blood donation trend in Malaysia"
    message2 = f"Alternatively, you can click on the menu button on the left of the chat box to select which output you prefer to see"
    message3 = f"Please note that it might take a while for the script to send the output"
    await context.bot.send_message(chat_id=update.message.chat_id, text=message)
    await context.bot.send_message(chat_id=update.message.chat_id, text=message2)
    await context.bot.send_message(chat_id=update.message.chat_id, text=message3)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    print(f'Update {update} caused error {context.error}')

# Responses
def handle_response(text: str) -> str:
    processed: str = text.lower()

    if 'hello' in processed:
        return 'Hey there! Please type /start to begin'
    
    return 'Please type /start to begin'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f'User ({update.message.chat.id}) un {message_type}: "{text}"')

    if message_type == 'group':
        if BOT_USERNAME in text: 
            new_text: str = text.replace(BOT_USERNAME, '').strip()
            response: str = handle_response(new_text)
        else:
            return
    else:
        response: str = handle_response(text)
    
    print('Bot:', response)
    await update.message.reply_text(response)


if __name__ == "__main__":
    print('Starting bot...')
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("malaysia", mytrend))
    app.add_handler(CommandHandler("regular", regtrend))
    app.add_handler(CommandHandler("state", statetrend))
    app.add_handler(CommandHandler("hospital", hospitaltrend))
    app.add_handler(CommandHandler("newdonors", agetrend))
    app.add_handler(CommandHandler("start", startcommand))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_error_handler(error)

    print('Polling...')
    app.run_polling() 