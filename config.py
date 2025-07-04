env_vars = {
  # Get From my.telegram.org
  "API_HASH": "29245477",
  # Get From my.telegram.org
  "API_ID": "0abc83883262245c90ca337b7a0375c4",
  #Get For @BotFather
  "BOT_TOKEN": "7845096754:AAGtGSwNYZrzKlD_rZrVTPNucq8dCl_iE1I",
  # Get For tembo.io
  "DATABASE_URL_PRIMARY": "postgresql+asyncpg://neondb_owner:npg_XbwV4SzKFn7G@ep-steep-feather-a8wgninx-pooler.eastus2.azure.neon.tech/neondb",
  # Logs Channel Username Without @
  "CACHE_CHANNEL": "ANTIKPOPSQUAD0000",
  # Force Subs Channel username without @
  "CHANNEL": "Anime_Eternals",
  # {chap_num}: Chapter Number
  # {chap_name} : Manga Name
  # Ex : Chapter {chap_num} {chap_name} @Manhwa_Arena
  "FNAME": "",
  # Put Thumb Link 
  "THUMB": "https://litter.catbox.moe/bxry4e.jpg"
}

dbname = env_vars.get('DATABASE_URL_PRIMARY') or env_vars.get('DATABASE_URL') or 'sqlite:///test.db'

if dbname.startswith('postgres://'):
    dbname = dbname.replace('postgres://', 'postgresql://', 1)
    
