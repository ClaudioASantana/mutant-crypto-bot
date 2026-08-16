import re

with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# Fix liveData.candle
content = re.sub(r'liveData\.candle\.open\.toFixed\(2\)', 'liveData.candle.open?.toFixed(2)', content)
content = re.sub(r'liveData\.candle\.close\.toFixed\(2\)', 'liveData.candle.close?.toFixed(2)', content)
content = re.sub(r'liveData\.candle\.high\.toFixed\(2\)', 'liveData.candle.high?.toFixed(2)', content)
content = re.sub(r'liveData\.candle\.low\.toFixed\(2\)', 'liveData.candle.low?.toFixed(2)', content)

# Fix simulatorState
content = re.sub(r'simulatorState\.balance\.toFixed\(2\)', '(simulatorState?.balance || 0).toFixed(2)', content)
content = re.sub(r'simulatorState\.pnl >= 0', '(simulatorState?.pnl || 0) >= 0', content)
content = re.sub(r'simulatorState\.pnl\.toFixed\(2\)', '(simulatorState?.pnl || 0).toFixed(2)', content)

content = re.sub(r'simulatorState\.risk &&', 'simulatorState?.risk &&', content)
content = re.sub(r'simulatorState\.risk\.leverage', '(simulatorState?.risk?.leverage || 1)', content)
content = re.sub(r'simulatorState\.risk\.next_margin\.toFixed\(2\)', '(simulatorState?.risk?.next_margin || 0).toFixed(2)', content)
content = re.sub(r'simulatorState\.risk\.consecutive_losses', '(simulatorState?.risk?.consecutive_losses || 0)', content)
content = re.sub(r'simulatorState\.risk\.stop_gain', '(simulatorState?.risk?.stop_gain || 1)', content)
content = re.sub(r'simulatorState\.risk\.stop_loss', '(simulatorState?.risk?.stop_loss || 1)', content)

content = re.sub(r'simulatorState\.pending && simulatorState\.pending\.length', '(simulatorState?.pending || []).length', content)
content = re.sub(r'simulatorState\.pending\.map', '(simulatorState?.pending || []).map', content)
content = re.sub(r'simulatorState\.history\.length', '(simulatorState?.history || []).length', content)
content = re.sub(r'simulatorState\.history\.map', '(simulatorState?.history || []).map', content)

# Fix tradePreview
content = re.sub(r'tradePreview\.current_price\.toLocaleString\(\)', 'tradePreview?.current_price?.toLocaleString()', content)
content = re.sub(r'tradePreview\.call_tp\.toLocaleString\(\)', 'tradePreview?.call_tp?.toLocaleString()', content)
content = re.sub(r'tradePreview\.call_sl\.toLocaleString\(\)', 'tradePreview?.call_sl?.toLocaleString()', content)
content = re.sub(r'tradePreview\.put_tp\.toLocaleString\(\)', 'tradePreview?.put_tp?.toLocaleString()', content)
content = re.sub(r'tradePreview\.put_sl\.toLocaleString\(\)', 'tradePreview?.put_sl?.toLocaleString()', content)

with open("frontend/src/app/page.tsx", "w") as f:
    f.write(content)

print("Patched!")
