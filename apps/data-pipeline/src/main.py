import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

def main():
    print("==========================================")
    print("Starting Historical Data Ingest Pipeline")
    print("==========================================")
    
    # Initialize connection to MT5 terminal
    # Since this runs inside Wine, it connects directly to the terminal64.exe running under the same prefix.
    # We retry to handle the startup race condition as the MT5 desktop GUI boots up in Wine.
    print("Waiting for MetaTrader 5 terminal to initialize...")
    initialized = False
    for retry in range(15):
        if mt5.initialize():
            initialized = True
            break
        print(f"MT5 terminal not ready yet, retrying in 3 seconds... (attempt {retry+1}/15)")
        time.sleep(3)
        
    if not initialized:
        print(f"Failed to initialize MT5, error: {mt5.last_error()}")
        return

    print("Connected to MT5 terminal successfully!")
    
    # Check account and terminal information
    terminal_info = mt5.terminal_info()
    account_info = mt5.account_info()
    
    if terminal_info is not None:
        print(f"MT5 Terminal Build: {terminal_info.build}")
    
    if account_info is not None:
        print(f"Logged in to account: {account_info.login}")
        print(f"Broker/Company: {account_info.company}")
        print(f"Balance: {account_info.balance} {account_info.currency}")
    else:
        print("Warning: Terminal is not logged in to a broker. Please login via VNC or API.")

    # Fetch EURUSD H1 candles
    symbol = "EURUSD"
    # Ensure symbol is visible in Market Watch
    mt5.symbol_select(symbol, True)
    
    print(f"Fetching H1 candles for {symbol}...")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
    
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        print(f"Successfully retrieved {len(rates)} candles.")
        print("Sample data from DataFrame:")
        print(df.head(5).to_string(index=False))
    else:
        print(f"Failed to retrieve rates for {symbol}. Make sure the terminal is fully connected.")

    # Shut down MT5 API connection
    mt5.shutdown()
    print("==========================================")
    print("Pipeline Ingest completed successfully!")
    print("==========================================")

if __name__ == "__main__":
    main()
