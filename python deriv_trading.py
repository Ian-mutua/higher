from flask import Flask, render_template, request, jsonify
import asyncio
import json
import websockets
from colorama import init, Fore  # For terminal colors
from datetime import datetime, timedelta

init(autoreset=True)  # Initialize colorama

app = Flask(__name__)

async def connect_to_websocket(api_token):
    uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"  # Deriv WebSocket endpoint
    return await websockets.connect(uri)

async def authenticate(websocket, api_token):
    auth_message = {"authorize": api_token}
    await websocket.send(json.dumps(auth_message))
    response = await websocket.recv()
    response_data = json.loads(response)

    if 'error' in response_data:
        raise ValueError(f"Authentication failed: {response_data['error']['message']}")

    # Extract initial balance from the response
    initial_balance = response_data['authorize']['balance']
    print(f"Initial Account Balance: {initial_balance}")
    return initial_balance

async def get_tick_history(websocket, symbol, window_size=100):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=window_size)
    
    history_message = {
        "ticks_history": symbol,
        "start": int(start_time.timestamp()),
        "end": int(end_time.timestamp()),
        "style": "ticks"
    }

    await websocket.send(json.dumps(history_message))
    response = await websocket.recv()
    response_data = json.loads(response)

    if 'error' in response_data:
        raise ValueError(f"Tick history request failed: {response_data['error']['message']}")

    return response_data['history']['prices']

async def analyze_market_trend(websocket, symbol, window_size=100):
    # Fetch tick history data
    tick_history = await get_tick_history(websocket, symbol, window_size)

    # Calculate trend
    if len(tick_history) > 1:
        if tick_history[-1] > tick_history[-2]:
            return 'up'  # Uptrend if the latest price is higher than the previous price
        elif tick_history[-1] < tick_history[-2]:
            return 'down'  # Downtrend if the latest price is lower than the previous price
        else:
            return 'flat'  # No clear trend if the latest price is the same as the previous price
    else:
        return 'unknown'  # Insufficient data to determine trend

async def execute_trade(websocket, stake):
    contract_type = "CALL"  # Only executing higher trades
    barrier = -0.21  # Entry point minus 0.21 for higher trades
    
    proposal_message = {
        "proposal": 1,
        "amount": stake,
        "basis": "stake",
        "contract_type": contract_type,
        "currency": "USD",
        "duration": 5,
        "duration_unit": "t",
        "symbol": "R_10",
        "barrier": barrier
    }

    await websocket.send(json.dumps(proposal_message))
    response = await websocket.recv()
    response_data = json.loads(response)

    if 'error' in response_data:
        raise ValueError(f"Proposal failed: {response_data['error']['message']}")

    proposal_id = response_data['proposal']['id']
    buy_message = {"buy": proposal_id, "price": stake}
    await websocket.send(json.dumps(buy_message))

    response = await websocket.recv()
    buy_response_data = json.loads(response)

    if 'error' in buy_response_data:
        raise ValueError(f"Buy failed: {buy_response_data['error']['message']}")

    contract_id = buy_response_data['buy']['contract_id']

    # Wait for the contract result
    while True:
        await websocket.send(json.dumps({"proposal_open_contract": 1, "contract_id": contract_id}))
        contract_response = await websocket.recv()
        contract_data = json.loads(contract_response)

        if contract_data.get('proposal_open_contract', {}).get('is_sold', False):
            profit_loss = contract_data['proposal_open_contract']['profit']
            trade_outcome = profit_loss > 0
            break

        await asyncio.sleep(1)  # Poll every second until the contract is sold

    return trade_outcome, profit_loss

def print_trade_info(trade_outcome, profit_loss, total_profit, balance):
    if trade_outcome:
        print(Fore.GREEN + f"Won! profit = {profit_loss}  total profit= {total_profit} Account Balance: {balance}")
    else:
        print(Fore.RED + f"Lost! profit = {profit_loss}  total profit= {total_profit} Account Balance: {balance}")

async def main(api_token, initial_stake, profit_target, symbol):
    websocket = await connect_to_websocket(api_token)
    await authenticate(websocket, api_token)

    total_profit = 0
    current_stake = initial_stake

    while total_profit < profit_target:
        # Analyze market trend
        trend = await analyze_market_trend(websocket, symbol)
        print(f"Market trend: {trend}")

        if trend == 'up':
            # Execute trade
            trade_outcome, profit_loss = await execute_trade(websocket, current_stake)
            total_profit += profit_loss
            balance = await authenticate(websocket, api_token)  # Get updated account balance
            print_trade_info(trade_outcome, profit_loss, total_profit, balance)

            if trade_outcome:
                current_stake = initial_stake  # Reset stake after a win
            else:
                                current_stake *= 3  # Increase stake after a loss

            if total_profit >= profit_target:
                print(Fore.CYAN + "Congratulations! You have achieved the profit target.")
                break

        await asyncio.sleep(1)  # Wait for 1 second before analyzing the market again

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/trade', methods=['POST'])
def trade():
    api_token = request.form['api_token']
    initial_stake = float(request.form['initial_stake'])
    profit_target = float(request.form['profit_target'])
    symbol = "R_10"  # Symbol for which you want to analyze the trend

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main(api_token, initial_stake, profit_target, symbol))

    return jsonify({'message': 'Trading completed'})

if __name__ == "__main__":
    app.run(debug=True)

