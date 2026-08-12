import pandas as pd
import pandas_ta as ta
df = pd.DataFrame({"close": [1,2,3,4,5]*10})
df.ta.bbands(length=20, std=2, append=True)
print(df.columns)
