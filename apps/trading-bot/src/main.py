import MetaTrader5 as mt5
import time
import sys

def main():
    print("==========================================")
    print("Starting Algorithmic Trading Bot Node")
    print("==========================================")
    
    # Initialize connection to MT5 terminal
    # Runs inside the WinePrefix using standard MT5 API bindings
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
    
    # Check account connection
    account = mt5.account_info()
    if account is not None:
        print(f"Trading account: {account.login} | Balance: {account.balance} {account.currency}")
    else:
        print("Warning: Terminal is not logged in to a broker.")
        
    symbol = "EURUSD"
    # Ensure symbol is active in Market Watch
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select symbol {symbol}")
        mt5.shutdown()
        return

    print(f"Monitoring ticks for {symbol}. Press Ctrl+C to stop.")
    
    iteration = 0
    try:
        # In a production environment, this is a persistent 'while True:' loop
        # For demonstration and verification, we run 15 iterations and then exit
        while iteration < 15:
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None:
                print(f"[Tick #{iteration+1}] Bid: {tick.bid} | Ask: {tick.ask} | Last: {tick.last}")
            else:
                print(f"[Tick #{iteration+1}] Waiting for {symbol} ticks from broker...")
                
            iteration += 1
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nBot stopped by user interrupt.")
    except Exception as e:
        print(f"\nBot encountered an error: {e}", file=sys.stderr)
    finally:
        # Graceful shutdown of connection
        mt5.shutdown()
        print("==========================================")
        print("Trading Bot shut down gracefully.")
        print("==========================================")

if __name__ == "__main__":
    main()
