import streamlit as st
import time
import yfinance as yf
from forex_python.converter import CurrencyRates
from yahoo_fin.stock_info import get_live_price
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import plotly.express as px
from main_stock_app import DATABASE_FILE_LOCATION
import sqlite3
import pandas as pd
from sqlite3 import Error
from binance.client import Client


def get_stocks_df(db_file):
    try:
        conn = sqlite3.connect(db_file)
        return pd.read_sql_query("SELECT * FROM stocks",conn)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()


def dashboard_process(state):
    st.title(":chart_with_upwards_trend: Dashboard page")
    st.header("Welcome "+ state.user_name + "!")
    st.write('Stock Overview')
    stock_table = st.empty()
    try:
        dataframe = create_df(get_stocks_df(DATABASE_FILE_LOCATION))
        dataframe = dataframe.round(2)
        stock_table.table(dataframe.style.applymap(color_negative_red))
    except: 
        pass

    st.header("Stock Purchase")
    stock_name = st.empty()
    stock_quantity = st.empty()
    stock_bought_price = st.empty()
    stock_fees = st.empty()

    stock_name = str(stock_name.text_input("Stock Code E.g AAPL, BABA").strip().upper())
    stock_quantity = stock_quantity.text_input("Quantity").strip()
    stock_bought_price = stock_bought_price.text_input("Bought Price (Stock Market's Currency: e.g STI in SGD, BABA in USD)").strip()
    stock_fees = stock_fees.text_input("Extra Fees (Commissions etc)").strip()
    
    add_button = st.empty()
    add_button_state = add_button.button("Submit")


    if add_button_state:
        stock_currency = str(yf.Ticker(stock_name).info.get('currency'))
        #All values in str
        try:
            existing_data = check_existence_of_stock_name(DATABASE_FILE_LOCATION,stock_name)
            existing_quantity = existing_data['Quantity']
            existing_price = existing_data['Bought_Price_Avg']
            total_stock_quantity = float(stock_quantity)+float(existing_quantity)
            stock_bought_price_weighted_avg = (float(existing_quantity)*float(existing_price) + float(stock_quantity)*float(stock_bought_price))/float(total_stock_quantity)
        except:
            total_stock_quantity = stock_quantity
            stock_bought_price_weighted_avg = stock_bought_price

        try:
            existing_fees = existing_data['Fees']
            total_stock_fees = stock_fees + existing_fees
            
        except:
            total_stock_fees = stock_fees

        add_items_to_database(DATABASE_FILE_LOCATION,stock_name,total_stock_quantity,stock_bought_price_weighted_avg,total_stock_fees,stock_currency)

        dataframe = create_df(get_stocks_df(DATABASE_FILE_LOCATION))
        stock_table.empty()
        stock_table.table(dataframe.style.applymap(color_negative_red))

        #Clear text input
        if stock_name and stock_quantity and stock_bought_price and stock_fees:
            stock_name.text_input("Stock Code E.g AAPL, BABA",key="stock_name").strip().upper()
            stock_quantity.text_input("Quantity",key="stock_quantity").strip()
            stock_bought_price.text_input("Bought Price (Stock Market's Currency: e.g STI in SGD, BABA in USD)",key="stock_price").strip()
            stock_fees.text_input("Extra Fees (Commissions etc)",key="stock_fees").strip()

        #Notify successfully added to database
        added_stock_msg = st.empty()
        added_stock_msg.write(stock_name+" added Successfully!")
        time.sleep(5)
        added_stock_msg = added_stock_msg.empty()

    
def color_negative_red(val):
    """
    Takes a scalar and returns a string with
    the css property `'color: red'` for negative
    strings, black otherwise.
    """
    color = 'black'
    if type(val) != str:
        color = 'red' if val < 0 else 'black'
    return 'color: %s' % color

def create_df(df):
    dict_colour_map = {}
    c = CurrencyRates()
    for index, row in df.iterrows():
        #Set all values from str to float
        quantity = float(row['Quantity'])
        bought_price = float(row['Bought_Price_Avg'])
        fees = float(row['Fees'])
        
        #Get SGD valued amount
        if row['Currency'] != 'SGD':
            exchange_rate = c.get_rate(row['Currency'], 'SGD')
        else: 
            exchange_rate = 1     
        
        df.at[index,'Market Price'] = get_live_price(row['Stock'])
        market_price = df.at[index,'Market Price']
        df.at[index,'Market Value'] = quantity*market_price
        market_value = df.at[index,'Market Value']
        df.at[index,'Market Value (SGD)'] = df.at[index,'Market Value'] * exchange_rate
        df.at[index,'Total Spent'] = (quantity * bought_price) + fees
        total_spent = df.at[index,'Total Spent']
        df.at[index,'Total Spent (SGD)'] = df.at[index,'Total Spent'] * exchange_rate
        df.at[index,'Profit/Loss'] = market_value - total_spent
        df.at[index,'Profit/Loss (%)']  = ((market_value -  total_spent) / market_value) * 100
    
    
    # Summary which deals with different markets
    st.write('Summary')
    summary_df = df.reindex(columns=['Profit/Loss','Profit/Loss (%)','Market Value','Total Spent','Currency']).groupby(['Currency']).agg('sum')
    summary_df['Profit/Loss (%)'] = ((summary_df['Market Value'] - summary_df['Total Spent']) / summary_df['Market Value']) *100
    st.table(summary_df)

    # # Final Tally (SGD)
    st.write('Final Table (SGD)')
    final_df = df.reindex(columns=['Market Value (SGD)','Total Spent (SGD)','Currency']).groupby(['Currency']).agg('sum')
    final_df_sgd = final_df.sum()
    final_df_sgd['Profit/Loss (SGD)'] = (final_df_sgd['Market Value (SGD)'] - final_df_sgd['Total Spent (SGD)'])
    final_df_sgd['Profit/Loss (%) (SGD)'] = round(((final_df_sgd['Market Value (SGD)'] - final_df_sgd['Total Spent (SGD)']) / final_df_sgd['Market Value (SGD)']) * 100,2)
    st.table(final_df_sgd)

    # Sort df in terms of currency then profit/loss amounts 
    df.sort_values(by=['Currency','Profit/Loss'],ascending=False,inplace=True)
    df.reset_index(inplace=True,drop=True) 

    #Plot Asset Allocation
    fig = px.pie(df, values=df['Total Spent (SGD)'], names=df['Stock'], title='Asset Allocation (SGD)')
    st.plotly_chart(fig)
    for index,row in final_df.iterrows():
        st.write(index+" is "+str(round((row['Total Spent (SGD)']/final_df_sgd['Total Spent (SGD)'])*100,2))+" %")

    #Plot Profit Allocation
    fig = px.pie(df, values=df['Market Value (SGD)']-df['Total Spent (SGD)'], names=df['Stock'], title='Profit Allocation (SGD)')
    st.plotly_chart(fig)
    for index,row in final_df.iterrows():
        st.write(index+" is "+str(round((row['Market Value (SGD)']/final_df_sgd['Market Value (SGD)'])*100,2))+" %")

    #Plot Stock profit comparison 
    fig = px.bar(df, y=df['Market Value (SGD)']-df['Total Spent (SGD)'], x=df['Stock'], title='Stock profit comparison (SGD)')
    fig.update_layout(xaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig)

    #Reorganise df columns
    columnsTitles = ['Stock', 'Market Price', 'Bought_Price_Avg','Profit/Loss','Profit/Loss (%)','Market Value','Total Spent','Quantity','Currency']
    df = df.reindex(columns=columnsTitles)   

    return df

def add_items_to_database(db_file,stock_name,stock_quantity,stock_bought_price_weighted_avg,stock_fees,stock_currency):
    try:
        conn = sqlite3.connect(db_file)
        print("INSERT INTO stocks (Stock,Bought_Price_Avg,Currency,Fees,Quantity) VALUES ('"+str(stock_name)+"',"+str(stock_bought_price_weighted_avg)+",'"+str(stock_currency)+"',"+str(stock_fees)+","+str(stock_quantity)+")")
        conn.execute("INSERT INTO stocks (Stock,Bought_Price_Avg,Currency,Fees,Quantity) VALUES ('"+stock_name+"',"+stock_bought_price_weighted_avg+",'"+stock_currency+"',"+stock_fees+","+stock_quantity+")")
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()


def check_existence_of_stock_name(db_file,stock_name):
    try:
        conn = sqlite3.connect(db_file)
        return pd.read_sql_query(("SELECT * FROM stocks WHERE Stock = "+stock_name),conn)
    except Error as e:
        raise Exception('stock does not exist yet')
        print(e)
    finally:
        if conn:
            conn.close()
            
    
            
        




