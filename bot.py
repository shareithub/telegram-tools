import json
import asyncio
import os
import glob
import shutil
import shareithub
from shareithub import shareithub
from telethon import TelegramClient
from telethon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.errors import SessionPasswordNeededError
import qrcode_terminal

CONFIG_FILE = "config.json"
shareithub()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_config(api_id, api_hash):
    config = {"api_id": api_id, "api_hash": api_hash}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)
    return config

def list_tele_sessions():
    return [os.path.basename(f) for f in glob.glob("tele_*.session")]

def rename_session_file(old_session, new_session):
    old_file = old_session + ".session"
    new_file = new_session + ".session"
    if os.path.exists(old_file):
        shutil.move(old_file, new_file)
        print(f"Session file telah diubah namanya menjadi {new_file}")
    else:
        print(f"Tidak ditemukan file session: {old_file}")

async def scrape_tele_chats(client):
    from telethon.tl.types import Channel, Chat
    dialogs = await client.get_dialogs()
    chats = [dialog.entity for dialog in dialogs if isinstance(dialog.entity, (Channel, Chat))]
    return chats

async def auto_join_channels(client):
    keyword = input("Masukkan keyword untuk mencari channel: ")
    result = await client(SearchRequest(
        q=keyword,
        limit=100
    ))
    if not result.chats:
        print("Tidak ditemukan channel dengan keyword tersebut.")
        return

    print("\n🔹 Channel yang ditemukan:")
    for idx, chat in enumerate(result.chats, start=1):
        name = chat.title if hasattr(chat, "title") and chat.title else getattr(chat, "username", str(chat.id))
        print(f"{idx}. {name} (ID: {chat.id})")
    
    print("\nPilih opsi join:")
    print("1. Join semua channel")
    print("2. Pilih channel tertentu")
    join_choice = input("Masukkan pilihan (1/2): ")
    if join_choice == "1":
        channels_to_join = result.chats
    elif join_choice == "2":
        selected_ids = input("Masukkan nomor channel yang ingin di-join (pisahkan dengan koma): ")
        try:
            selected_indexes = [int(idx.strip()) - 1 for idx in selected_ids.split(",")]
            channels_to_join = [result.chats[i] for i in selected_indexes if 0 <= i < len(result.chats)]
        except Exception as e:
            print(f"🚫 Terjadi kesalahan dalam pemilihan: {e}")
            return
    else:
        print("Pilihan tidak valid. Membatalkan proses join.")
        return

    for chat in channels_to_join:
        try:
            await client(JoinChannelRequest(chat))
            name = chat.title if hasattr(chat, "title") and chat.title else getattr(chat, "username", str(chat.id))
            print(f"✅ Berhasil join ke channel: {name} (ID: {chat.id})")
        except Exception as e:
            print(f"⚠️ Gagal join ke channel {chat.id}: {e}")
        await asyncio.sleep(10)

async def telethon_manage(session_name, config):
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.connect()

    session_file = session_name + ".session"
    if os.path.exists(session_file):
        try:
            os.chmod(session_file, 0o600)
        except Exception as e:
            print(f"Error setting file permission for {session_file}: {e}")

    if not await client.is_user_authorized():
        print("Session belum terautorisasi. Silakan pilih metode login:")
        print("1. QR Code")
        print("2. Nomor Telepon")
        login_choice = input("Masukkan pilihan (1/2): ")

        if login_choice == "1":
            print("Memulai login dengan QR Code...")
            while True:
                try:
                    qr = await client.qr_login()
                    qrcode_terminal.draw(qr.url)
                    print("Silakan scan QR Code di atas dengan aplikasi Telegram.")
                    await asyncio.wait_for(qr.wait(), timeout=60)
                    print("QR Code berhasil discan!")
                    break
                except asyncio.TimeoutError:
                    print("QR Code tidak discan dalam 60 detik. Mengenerate ulang...")
                except SessionPasswordNeededError:
                    password = input("🔐 Masukkan password verifikasi dua langkah: ")
                    await client.sign_in(password=password)
                    break
                except Exception as e:
                    print(f"Error saat QR login: {e}")
                    return
        elif login_choice == "2":
            phone = input("Masukkan nomor telepon Anda (dengan kode negara, misal +628xxx): ")
            try:
                await client.start(phone=phone)
            except Exception as e:
                print(f"Error saat login dengan nomor telepon: {e}")
                return
        else:
            print("Pilihan tidak valid.")
            await client.disconnect()
            return
    else:
        print("Session yang dipilih sudah terautorisasi, melewati langkah login.")

    me = await client.get_me()
    phone = getattr(me, "phone", None)
    new_session_name = f"tele_{phone}" if phone else f"tele_{me.id}"
    if session_name != new_session_name:
        rename_session_file(session_name, new_session_name)
        session_name = new_session_name

    print(f"\nLogin berhasil sebagai: {me.first_name} ({me.id}), session: {session_name}")

    print("\nPilih operasi:")
    print("1. Unsubscribe dari channel/grup")
    print("2. Auto join channel berdasarkan keyword")
    operation_choice = input("Masukkan pilihan (1/2): ")

    if operation_choice == "1":
        chats = await scrape_tele_chats(client)
        if not chats:
            print("⚠️ Tidak ada channel/grup yang terdeteksi pada akun ini.")
            if os.path.exists(session_file):
                os.chmod(session_file, 0o600)
            await client.disconnect()
            return

        print("\n🔹 Daftar Channel/Grup yang Diikuti:")
        for idx, chat in enumerate(chats, start=1):
            name = chat.title if hasattr(chat, "title") and chat.title else getattr(chat, "username", str(chat.id))
            print(f"{idx}. {name} (ID: {chat.id})")

        print("\n❓ Pilih opsi unsubscribe:")
        print("1. Keluar dari semua channel/grup")
        print("2. Pilih channel/grup tertentu")
        pilihan = input("Masukkan pilihan (1/2): ")

        if pilihan == "1":
            selected_chats = chats
        elif pilihan == "2":
            selected_ids = input("Masukkan nomor channel/grup yang ingin di-unsubscribe (pisahkan dengan koma): ")
            try:
                selected_indexes = [int(idx.strip()) - 1 for idx in selected_ids.split(",")]
                selected_chats = [chats[i] for i in selected_indexes if 0 <= i < len(chats)]
            except Exception as e:
                print(f"🚫 Terjadi kesalahan dalam pemilihan: {e}")
                if os.path.exists(session_file):
                    os.chmod(session_file, 0o600)
                await client.disconnect()
                return
        else:
            print("🚫 Pilihan tidak valid.")
            if os.path.exists(session_file):
                os.chmod(session_file, 0o600)
            await client.disconnect()
            return

        for chat in selected_chats:
            try:
                await client(LeaveChannelRequest(chat.id))
                name = chat.title if hasattr(chat, "title") and chat.title else getattr(chat, "username", str(chat.id))
                print(f"✅ Berhasil keluar dari: {name} (ID: {chat.id})")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"⚠️ Gagal keluar dari {chat.id}: {e}")

        print("✅ Selesai dengan operasi unsubscribe!")
    elif operation_choice == "2":
        await auto_join_channels(client)
    else:
        print("Pilihan operasi tidak valid.")

    if os.path.exists(session_file):
        os.chmod(session_file, 0o600)
    await client.disconnect()

def main():
    config = load_config()
    if config is None:
        print("File config.json tidak ditemukan. Mohon masukkan API ID dan API Hash.")
        api_id = input("Masukkan API ID: ")
        api_hash = input("Masukkan API Hash: ")
        config = save_config(api_id, api_hash)

    tele_sessions = list_tele_sessions()
    if tele_sessions:
        print("Daftar akun (session) Telethon yang tersimpan:")
        for idx, sess in enumerate(tele_sessions, start=1):
            print(f"{idx}. {sess}")
        print("0. Login baru")
        pilihan = input("Pilih akun yang akan digunakan (masukkan nomor, atau 0 untuk login baru): ")
        if pilihan.isdigit() and int(pilihan) > 0:
            idx = int(pilihan) - 1
            sess = tele_sessions[idx]
            asyncio.run(telethon_manage(sess.replace(".session", ""), config))
            return
            
    asyncio.run(telethon_manage("temp_tele", config))

if __name__ == "__main__":
    main()
