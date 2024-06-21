import discord
from discord.ext import commands
import mysql.connector
from config import TOKEN, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
from datetime import datetime
import pytz

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix='/', intents=intents)

ALLOWED_USER_IDS = [
    your id
]

async def dodaj_do_bazy(user_id, user_name, blocked_id, blocked_name, reason, response):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM blacklisted_users WHERE blocked_id = %s", (blocked_id,))
        if c.fetchone()[0] > 0:
            print(f"Użytkownik z ID: {blocked_id} już istnieje na liście zablokowanych.")
            return False

        current_time_poland = datetime.now(pytz.timezone('Europe/Warsaw'))
        current_time_poland_str = current_time_poland.strftime('%Y-%m-%d %H:%M:%S')

        c.execute(
            "INSERT INTO blacklisted_users (user_id, user_name, blocked_id, blocked_name, reason, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, user_name, blocked_id, blocked_name, reason, current_time_poland_str)
        )
        conn.commit()
        print(f"Dodano użytkownika: {blocked_name}, {blocked_id} do listy zablokowanych przez {user_name} o {current_time_poland_str}")
        return True
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        if conn.is_connected():
            c.close()
            conn.close()

async def usun_z_bazy(entry_id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        c = conn.cursor()

        c.execute("SELECT blocked_id FROM blacklisted_users WHERE id = %s", (entry_id,))
        row = c.fetchone()
        if not row:
            return None

        blocked_id = row[0]

        c.execute("DELETE FROM blacklisted_users WHERE id = %s", (entry_id,))
        conn.commit()
        print(f"Usunięto wpis z ID: {entry_id} i odbanowano użytkownika z ID: {blocked_id}")

       
        c.execute("SET @count = 0")
        c.execute("UPDATE blacklisted_users SET id = @count:= @count + 1 ORDER BY id")
        conn.commit()

        return blocked_id
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        if conn.is_connected():
            c.close()
            conn.close()

async def get_random_message():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        c = conn.cursor()
        c.execute("SELECT response FROM blacklisted_users ORDER BY RAND() LIMIT 1")
        row = c.fetchone()
        return row[0] if row else None
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        if conn.is_connected():
            c.close()
            conn.close()

async def get_blacklisted_users():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        c = conn.cursor()
        c.execute("SELECT id, user_id, user_name, blocked_id, blocked_name, reason, timestamp FROM blacklisted_users")
        rows = c.fetchall()
        return rows
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []
    finally:
        if conn.is_connected():
            c.close()
            conn.close()

def is_allowed_user(ctx):
    return ctx.author.id in ALLOWED_USER_IDS

@client.event
async def on_ready():
    print('Czachownik na pozycji')
    await client.change_presence(activity=discord.Game(name="Rozpierdalanie sie na komendzie"))

@client.command()
@commands.check(is_allowed_user)
async def dodaj(ctx, blocked_id: str = None, blocked_name: str = None, *, reason: str = None):
    if blocked_id is None or blocked_name is None or reason is None:
        await ctx.send("Użycie: /dodaj <id> <nick> <powód>")
        return

    user_id = str(ctx.author.id)
    user_name = str(ctx.author.name)

    if not blocked_id.isdigit():
        await ctx.send("Użycie: /dodaj <id> <nick> <powód>")
        return

    response = "Brak odpowiedzi"

    if await dodaj_do_bazy(user_id, user_name, blocked_id, blocked_name, reason, response):
        
        for guild in client.guilds:
            try:
                await guild.ban(discord.Object(id=int(blocked_id)), reason=reason)
            except discord.Forbidden:
                pass 
            except discord.HTTPException as e:
                pass  

        await ctx.send(f"Użytkownik {blocked_name}, {blocked_id} został zbanowany na wszystkich serwerach.")
    else:
        await ctx.send(f"Użytkownik z ID: {blocked_id} już istnieje na liście zablokowanych.")

@client.command()
@commands.check(is_allowed_user)
async def lista(ctx):
    users = await get_blacklisted_users()
    if not users:
        await ctx.send("Brak zablokowanych użytkowników.")
        return

    message = "Zablokowani użytkownicy:\n"
    chunks = [users[i:i+5] for i in range(0, len(users), 5)] 
    index = 1
    for chunk in chunks:
        chunk_message = ""
        for user in chunk:
            timestamp = user[6].strftime('%Y-%m-%d %H:%M:%S')
            chunk_message += f" Nr: {user[0]}, ID gracza: {user[3]}, Nick: {user[4]}, Powód: {user[5]}, Data: {timestamp}, dodany przez: {user[2]} o ID: {user[1]}\n"
            index += 1
        await ctx.send(chunk_message)

@client.command()
@commands.check(is_allowed_user)
async def wypierdol(ctx):
    users = await get_blacklisted_users()
    if not users:
        await ctx.send("Brak zablokowanych użytkowników.")
        return

    for user in users:
        blocked_id = user[3]
        blocked_name = user[4]
        try:
            await ctx.guild.ban(discord.Object(id=int(blocked_id)), reason="Zbanowany przez /wypierdol")
        except discord.Forbidden:
            await ctx.send(f"Bot nie ma uprawnień do banowania użytkownika {blocked_name} na tym serwerze.")
        except discord.HTTPException as e:
            await ctx.send(f"Wystąpił błąd podczas banowania użytkownika {blocked_name} na tym serwerze: {e}")
    await ctx.send("Zbanowano wszystkich użytkowników z listy na tym serwerze.")

@client.command()
@commands.check(is_allowed_user)
async def czacha(ctx):
    commands_list = "/dodaj <id> <nick> <powod> - Dodaje użytkownika do zablokowanych i banuje na wszystkich serwerach.\n"
    commands_list += "/lista - Wyświetla listę zablokowanych użytkowników.\n"
    commands_list += "/wypierdol - Banuje wszystkich zablokowanych użytkowników na bieżącym serwerze.\n"
    commands_list += "/usun <nr> - Usuwa wpis z bazy danych i odbanowuje użytkownika na wszystkich serwerach.\n"
    await ctx.send(f"Dostępne komendy:\n{commands_list}")

@client.command()
@commands.check(is_allowed_user)
async def usun(ctx, entry_id: int):
    blocked_id = await usun_z_bazy(entry_id)
    if blocked_id:
       
        for guild in client.guilds:
            try:
                async for ban_entry in guild.bans():
                    if ban_entry.user.id == int(blocked_id):
                        await guild.unban(ban_entry.user)
                        break
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                pass 

        await ctx.send(f"Usunięto wpis o numerze {entry_id} i odbanowano użytkownika o ID {blocked_id} na wszystkich serwerach.")
    else:
        await ctx.send(f"Nie znaleziono wpisu o numerze {entry_id}.")

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("Brak uprawnień.")
    else:
        await ctx.send(f"Wystąpił błąd: {error}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    await client.process_commands(message)

client.run(TOKEN)
