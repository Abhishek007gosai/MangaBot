env_vars = {
  # Get From my.telegram.org
  "API_HASH": "c9599a5aa61ee8ca4f5e778d20c61f24",
  # Get From my.telegram.org
  "API_ID": "23537462",
  #Get For @BotFather
  "BOT_TOKEN": "",
  # Get For tembo.io
  "DATABASE_URL_PRIMARY": "postgresql://postgres:animehub69@@db.zsgvpdlijpjitfpssllf.supabase.co:5432/postgres",
  # Logs Channel Username Without @
  "CACHE_CHANNEL": "ANTIKPOPSQUAD0000",
  # Force Subs Channel username without @
  "CHANNEL": "Anime_Eternals",
  # {chap_num}: Chapter Number
  # {chap_name} : Manga Name
  # Ex : Chapter {chap_num} {chap_name} @Manhwa_Arena
  "FNAME": "",
  # Put Thumb Link 
  "THUMB": "https://litter.catbox.moe/dhhhnb2f17db0977.jpg"
}

dbname = env_vars.get('DATABASE_URL_PRIMARY') or env_vars.get('DATABASE_URL') or 'sqlite:///test.db'

if dbname.startswith('postgres://'):
    dbname = dbname.replace('postgres://', 'postgresql://', 1)
    
