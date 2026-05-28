import os
p = r"C:\Users\win\AppData\Local\Temp\stt_temp_-6734442141547153466.wav"
print(p)
print('exists=', os.path.exists(p))
print('size=', os.path.getsize(p) if os.path.exists(p) else 'N/A')
