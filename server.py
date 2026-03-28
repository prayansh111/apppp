import asyncio
import json
import os
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from google.cloud import firestore

# 1. SETUP FIREBASE (Replace with your Project ID)
db = firestore.Client(project="fast-file-transfer-9ec05")

async def run_receiver():
    # WebRTC Config (Using Google's STUN server)
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc = RTCPeerConnection(configuration=config)
    
    # 6-Digit Code Setup
    import random
    room_code = str(random.randint(100000, 900000))
    print(f"🚀 Your Pairing Code: {room_code}")
    room_ref = db.collection("rooms").doc(room_code)

    file_meta = {}
    received_size = 0
    file_writer = None

    @pc.on("datachannel")
    def on_datachannel(channel):
        nonlocal file_writer, received_size, file_meta
        
        @channel.on("message")
        def on_message(message):
            nonlocal file_writer, received_size, file_meta
            
            # If message is text, it's the filename/size
            if isinstance(message, str):
                file_meta = json.loads(message)
                save_path = os.path.expanduser(f"~/Downloads/{file_meta['name']}")
                file_writer = open(save_path, "wb")
                print(f"📥 Receiving: {file_meta['name']} ({file_meta['size']} bytes)")
            
            # If message is bytes, it's the file data
            else:
                file_writer.write(message)
                received_size += len(message)
                percent = (received_size / file_meta['size']) * 100
                print(f"📊 Progress: {percent:.1f}%", end="\r")
                
                if received_size >= file_meta['size']:
                    file_writer.close()
                    print(f"\n✅ File saved to Downloads!")

    # CREATE THE OFFER
    await pc.createDataChannel("fileTransfer")
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # SEND OFFER TO FIREBASE
    room_ref.set({
        "offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    })

    print("📡 Waiting for phone to connect...")

    # WAIT FOR ANSWER FROM FIREBASE
    while True:
        snap = room_ref.get().to_dict()
        if snap and "answer" in snap:
            answer = RTCSessionDescription(sdp=snap["answer"]["sdp"], type=snap["answer"]["type"])
            await pc.setRemoteDescription(answer)
            print("🤝 Connected to Phone!")
            break
        await asyncio.sleep(1)

    # Keep script running during transfer
    await asyncio.sleep(3600) 

if __name__ == "__main__":
    asyncio.run(run_receiver())