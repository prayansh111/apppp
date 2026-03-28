import asyncio
import json
import os
import random
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from google.cloud import firestore

# 1. SETUP AUTHENTICATION
# Ensure serviceAccount.json is in the same folder as this script
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "serviceAccount.json"
db = firestore.Client()

async def run_receiver():
    # WebRTC Setup using Google STUN server
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc = RTCPeerConnection(configuration=config)
    
    # Generate 6-digit Pairing Code
    room_code = str(random.randint(100000, 900000))
    print(f"\n🚀 MAC READY | PAIRING CODE: {room_code}")
    print("------------------------------------------")
    
    room_ref = db.collection("rooms").doc(room_code)
    file_writer = None
    received_size = 0
    file_meta = {}

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel.binaryType = "bytes"
        print("🤝 Phone connected! Receiving stream...")

        @channel.on("message")
        def on_message(message):
            nonlocal file_writer, received_size, file_meta
            
            if isinstance(message, str):
                file_meta = json.loads(message)
                save_path = os.path.expanduser(f"~/Downloads/{file_meta['name']}")
                file_writer = open(save_path, "wb")
                print(f"📥 Filename: {file_meta['name']}")
            else:
                file_writer.write(message)
                received_size += len(message)
                percent = (received_size / file_meta['size']) * 100
                print(f"📊 Progress: {percent:.1f}% | {received_size // 1048576} MB", end="\r")
                
                if received_size >= file_meta['size']:
                    file_writer.close()
                    print(f"\n✅ SUCCESS: File saved to Downloads!")

    # Create Data Channel and Offer
    await pc.createDataChannel("fileTransfer")
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Push offer to Firebase
    room_ref.set({"offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}})
    print("📡 Waiting for Phone to enter the code...")

    # Wait for Answer from Phone
    while True:
        snap = room_ref.get().to_dict()
        if snap and "answer" in snap:
            answer = RTCSessionDescription(sdp=snap["answer"]["sdp"], type=snap["answer"]["type"])
            await pc.setRemoteDescription(answer)
            break
        await asyncio.sleep(1)

    await asyncio.sleep(86400) # Keep script running for 24 hours

if __name__ == "__main__":
    asyncio.run(run_receiver())