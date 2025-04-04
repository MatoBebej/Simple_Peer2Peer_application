import socket
import struct
import threading
import time
import os
import random

# global variables
connected = False
running = True
kal_counter = 0
prev_data = b""
fragment_size = 0
file_place = ""
file_name = ""
file_fragments = {}
stop = True
time_limit = 15
my_timer = time.time()
switcher = 0
err = 0
file_timer = time.time()
file_timer_switch = 0
total_time = time.time()
mess_frag_size = 0
final_messege = ""
all_frag = 0
bad = 0
biggest = 0
smallest = 0

# Host and guest IPs and ports for two-way communication
host = "127.0.0.1"  # Local IP
guest = "127.0.0.1"  # Peer IP (assumes localhost for testing)
send_port = 20050  # Peer port to which we send data
receive_port = 20060  # Local port on which we listen for incoming data

'''
# inputs to set ports and IPs
host = input("Enter the your address of the peer (e.g., 127.0.0.1): ")
guest = input("Enter the guest address of the peer (e.g., 127.0.0.1): ")
receive_port = int(input("Enter your port number to receive data: "))
send_port = int(input("Enter guest port number to send data: "))
'''
#flag definitions
SYN = 0b00000001  # SYN for starting handshake
ACK = 0b00000010  # ACK for acknowledging receipt
END = 0b00000100  # End communication
KAL = 0b00001000  # Keep Alive -> for heartbeat
ERROR = 0b00010000  # When you want to currupt message/file
FILE = 0b00100000  # File transfer
MESSAGE = 0b01000000  # Message transfer indicator
NAME = 0b10000000  # name of the file

#creation of udp_socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # ?
udp_socket.bind((host, receive_port))  # Bind to the receiving port

p_a = (guest, send_port)


#create header function
def create_header(seq_num, window_size, flags, data_length, checksum):
    # Pack header fields into bytes
    header = struct.pack('!IHBHH', seq_num, window_size, flags, data_length, checksum)
    return header

#guide to all the commands
def guide():
    print("here is the guide of all the commands:")
    print("handshake -> needed to establish connection between peers")
    print("exit -> needed to close connection between peers")
    print("mess_error -> needed to currupt message (it will be resent the same message one more time")
    print("mess_frag -> if we want to send messege via fragments")
    print("flag_size -> needed to set the frag_size for file transfer")
    print("file -> needed to send the file")
    print("file_loc -> path to file which we want to sent")
    print("file_error -> needed to currupt one of the file fragments")
    print("guide -> needed to see explanation of all commands")
    print("'' -> needed to send the text")

#function to calculte checksum of the data
def calculate_checksum(data):
    """Calculate CRC16 checksum for the given data."""
    poly = 0x1021
    crc = 0xFFFF

    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF

    return crc


#handshake start function
def initiate_handshake(peer_addr, seq_num, window_size):
    global connected
    #send SYN packet with SYN flag (00000001)
    flags = SYN
    header = create_header(seq_num, window_size, flags, data_length=0, checksum=0)
    udp_socket.sendto(header, peer_addr)
    print("Sent SYN packet to start handshake")


def keep_alive():
    global kal_counter
    global running
    global connected
    while running:  #while the peers ale online
        time.sleep(0.001)
        if connected:
            if stop == False:  #skip sending KAL if stopped
                time.sleep(1)
                kal_counter = 0
                continue
            # Send a KAL message
            flags = KAL
            header = create_header(seq_num=0, window_size=0, flags=flags, data_length=0, checksum=0)
            udp_socket.sendto(header, p_a)
            # print("Sent KAL packet")
            #check if the KAL counter or timer has exceeded limits
            if kal_counter >= 4 or (time.time() - my_timer > time_limit):
                print("No response to keep-alive packets. Terminating connection.")
                running = False
                udp_socket.close()
                return
            #wait for a response (5-second timeout)
            time.sleep(5)
            kal_counter += 1  #increment counter if no response
            # print(f"KAL counter incremented to {kal_counter}")
        else:
            time.sleep(2)
    time.sleep(2)

#fucntion for sending messege fragmets (copy of send_file)
def send_frag_mess(data, peer_addr):
    global err
    global stop
    global switcher
    global running
    global file_timer
    global mess_frag_size
    global all_frag
    global bad
    global biggest
    global smallest

    if mess_frag_size == 0:
        if err == 1:
            checksum = calculate_checksum(data) + 1
            err = 0
        else:
            checksum = calculate_checksum(data)
        custom_flags = (MESSAGE | END)
        header = create_header(seq_num=0, window_size=1, flags=custom_flags, data_length=len(data), checksum=checksum)
        packet = header + data
        udp_socket.sendto(packet, peer_addr)
        biggest = len(data)
        smallest = len(data)
        return
    else:
        num_of_frag = (len(data) + mess_frag_size - 1) // mess_frag_size
        print(f"Total fragments: {num_of_frag}")
        if err == 1:
            error_place = random.randint(0, num_of_frag - 1)
            print(f"error will happen in step {error_place + 1}")
        curr_place = 0
        retries = 0
        max_retries = 3
        timeout_count = 0
        my_pos = curr_place
        while curr_place < num_of_frag and running:
            mess_frag = data[my_pos:my_pos + mess_frag_size]
            my_pos = my_pos + mess_frag_size
            print(mess_frag)
            if err == 1 and error_place == curr_place:
                checksum = calculate_checksum(mess_frag) + 1
                err = 0
            else:
                checksum = calculate_checksum(mess_frag)
            header = create_header(seq_num=curr_place, window_size=1, flags=MESSAGE, data_length=len(mess_frag), checksum=checksum)
            packet = header + mess_frag
            udp_socket.sendto(packet, peer_addr)
            print(f"Sent mess fragment {curr_place + 1}/{num_of_frag} with size {len(mess_frag)}")
            if smallest > len(mess_frag) or smallest == 0:
                smallest = len(mess_frag)
            if biggest < len(mess_frag):
                biggest = len(mess_frag)
            file_timer = time.time()
            all_frag += 1
            # from here

            while running and connected:
                try:
                    if time.time() - file_timer < 5:
                        if switcher == 2:  # switcher == 2 -> ze MESSEGE | ACK / ERROR prijala recieve_messege funkcia
                            stop = False  # vypnutie kal
                            timeout_count = 0
                            ack_seq, _, flags, _, _ = struct.unpack('!IHBHH', msg[:11])
                            switcher = 0
                            if flags == (MESSAGE | ACK) and ack_seq == curr_place:
                                print(f"Received FILE | ACK for fragment {curr_place + 1}")
                                curr_place += 1
                                retries = 0  #reset retries on successful acknowledgment
                                break
                            elif flags == (MESSAGE | ERROR) and ack_seq == curr_place:
                                print(f"Received MESSAGE | ERROR for fragment {curr_place + 1}, resending...")
                                checksum = calculate_checksum(mess_frag)
                                header = create_header(seq_num=curr_place, window_size=1, flags=MESSAGE,
                                                       data_length=len(mess_frag), checksum=checksum)
                                packet = header + mess_frag
                                udp_socket.sendto(packet, peer_addr)
                                retries += 1
                                bad += 1
                                all_frag += 1
                                if retries >= max_retries:
                                    print(
                                        f"Messege fragment {curr_place + 1} failed after {max_retries} retries. Stopping messege transfer.")
                                    return

                        else:
                            time.sleep(0.001)
                    else:
                        print(f"timeout counter: {timeout_count}")
                        if timeout_count >= max_retries:
                            print("second peer is offline")
                            udp_socket.close()
                            running = False
                            return
                        else:
                            timeout_count += 1
                            print("second peer is not responding, resending")
                            header = create_header(seq_num=curr_place, window_size=1, flags=MESSAGE,
                                                   data_length=len(mess_frag), checksum=checksum)
                            all_frag += 1
                            bad += 1
                            packet = header + mess_frag
                            udp_socket.sendto(packet, peer_addr)
                            print(f"Sent fragment {curr_place + 1}/{num_of_frag} with size {len(mess_frag)}")
                            time.sleep(5)
                            file_timer = time.time()


                except socket.timeout:
                    printf("error")

        #send FILE | END to indicate completion
        if running:
            end_header = create_header(seq_num=0, window_size=0, flags=(MESSAGE | ACK | END), data_length=0, checksum=0)
            udp_socket.sendto(end_header, peer_addr)
            print("Messege transfer completed.")
            mess_frag_size = 0
            print("štatistika -> ")
            print("počet všetkých fragmentov -> ", all_frag)
            print("počet zlých fragmentov -> ", bad)
            print("najmensi frag ->", smallest)
            print("najvacsi frag ->", biggest)
            smallest = 0
            biggest = 0
            bad = 0
            all_frag = 0
            return

#function for receiving and collecting mess_fragments
def receive_frag_messege(seq_num, flags, data_length, checksum, payload, addr):
    global final_messege
    global running
    global connected
    global kal_counter
    global my_timer
    global stop
    global mess_frag_size

    if flags == (MESSAGE | ACK | END):
        print("Messege transfer completed.")
        print(f"the proces took {time.time() - total_time} seconds")
        udp_socket.settimeout(None)
        print(f"message is {final_messege}")
        final_messege = ""
        mess_frag_size = 0

        custom_flags = END | NAME | ACK
        kal_back_header = create_header(seq_num=0, window_size=1, flags=custom_flags, data_length=0, checksum=0)
        udp_socket.sendto(kal_back_header, addr)
        print("renewing kal")
        kal_counter = 0
        my_timer = time.time()
        stop = True
        return

    if flags == MESSAGE:
        stop = False
        if checksum == calculate_checksum(payload):
            print(f"Received fragment {seq_num + 1}, adding to messege fragments")
            # print(f"Type of payload for fragment {seq_num}: {type(payload)}")
            final_messege += payload.decode()  # Store the fragment by its sequence number
            #send acknowledgment for the received fragment
            response_flags = MESSAGE | ACK
            response_header = create_header(seq_num, window_size=1, flags=response_flags, data_length=0, checksum=0)
            udp_socket.sendto(response_header, addr)
            print(f"Sent ACK for fragment {seq_num + 1}")
        else:
            print(f"Received fragment {seq_num + 1}, but checksum mismatch -> resending...")
            response_flags = MESSAGE | ERROR
            response_header = create_header(seq_num, window_size=1, flags=response_flags, data_length=0, checksum=0)
            udp_socket.sendto(response_header, addr)

#function for sending file fragments
def send_file(peer_addr):
    """Send a file using Stop-and-Wait protocol with error handling."""
    global file_place
    global fragment_size
    global stop
    global running
    global connected
    global switcher
    global err
    global file_timer
    global all_frag
    global bad
    global smallest
    global biggest
    timeout_count = 0

    stop = False
    if not os.path.isfile(file_place):
        print("Invalid file path.")
        return
    print("file path:", file_place)
    file_size = os.path.getsize(file_place)
    print(f"File size: {file_size} bytes")
    total_fragments = (file_size + fragment_size - 1) // fragment_size  #calculate number of fragments
    print(f"Total fragments: {total_fragments}")

    seq_num = 0 #my position
    retries = 0  #track consecutive retries
    max_retries = 3

    if err == 1:
        err_place = random.randint(0, 10)
        print("err place is ", err_place)

    with open(file_place, 'rb') as file:
        while seq_num < total_fragments and running:
            fragment = file.read(fragment_size)
            if err == 1 and err_place == seq_num:
                checksum = calculate_checksum(fragment) + 1
                err = 0
            else:
                checksum = calculate_checksum(fragment)
            header = create_header(seq_num=seq_num, window_size=1, flags=FILE, data_length=len(fragment),
                                   checksum=checksum)
            packet = header + fragment
            udp_socket.sendto(packet, peer_addr)
            print(f"Sent fragment {seq_num}/{total_fragments} with size {len(fragment)}")
            all_frag += 1
            if smallest > len(fragment) or smallest == 0:
                smallest = len(fragment)
            if biggest < len(fragment):
                biggest = len(fragment)
            file_timer = time.time()

            #wait for FILE | ACK or FILE | ERROR response
            while running and connected:
                try:
                    if time.time() - file_timer < 5:
                        if switcher == 1:  #switcher == 1 -> ze FILE | ACK / ERROR prijala recieve_messege funkcia
                            stop = False  #vypnutie kal
                            timeout_count = 0
                            ack_seq, _, flags, _, _ = struct.unpack('!IHBHH', msg[:11])
                            switcher = 0
                            if flags == (FILE | ACK) and ack_seq == seq_num:
                                print(f"Received FILE | ACK for fragment {seq_num}")
                                seq_num += 1
                                retries = 0  #reset retries on successful acknowledgment
                                break
                            elif flags == (FILE | ERROR) and ack_seq == seq_num:
                                print(f"Received FILE | ERROR for fragment {seq_num}, resending...")
                                checksum = calculate_checksum(fragment)
                                header = create_header(seq_num=seq_num, window_size=1, flags=FILE,
                                                       data_length=len(fragment), checksum=checksum)
                                all_frag += 1
                                bad += 1
                                packet = header + fragment
                                udp_socket.sendto(packet, peer_addr)
                                retries += 1
                                if retries >= max_retries:
                                    print(
                                        f"Fragment {seq_num} failed after {max_retries} retries. Stopping file transfer.")
                                    return

                        else:
                            time.sleep(0.001)
                    #my own kal for this fucntion (if second peer is not responding)
                    else:
                        print(timeout_count)
                        if timeout_count >= max_retries:
                            print("second peer is offline")
                            udp_socket.close()
                            running = False
                            return
                        else:
                            timeout_count += 1
                            print("second peer is not responding, resending")
                            header = create_header(seq_num=seq_num, window_size=1, flags=FILE,
                                                   data_length=len(fragment), checksum=checksum)
                            packet = header + fragment
                            udp_socket.sendto(packet, peer_addr)
                            all_frag += 1
                            bad += 1
                            print(f"Sent fragment {seq_num}/{total_fragments}")
                            time.sleep(5)
                            file_timer = time.time()


                except socket.timeout:
                    printf("error")

        #send FILE | END to indicate completion
        if running:
            end_header = create_header(seq_num=0, window_size=0, flags=(FILE | END), data_length=0, checksum=0)
            udp_socket.sendto(end_header, peer_addr)
            print("File transfer completed.")
            print("štatistika -> ")
            print("počet všetkých fragmentov -> ", all_frag)
            print("počet zlých fragmentov -> ", bad)
            bad = 0
            all_frag = 0
            print("najmensi frag ->", smallest)
            print("najvacsi frag ->", biggest)
            smallest = 0
            biggest = 0
            return


def receive_file(seq_num, flags, data_length, checksum, payload, addr):
    global running
    global file_place
    global fragment_size
    global file_fragments
    global stop
    global kal_counter
    global my_timer

    if flags == (FILE | END):  #if we received the END flag
        print("File transfer completed.")
        print(f"the proces took {time.time() - total_time} seconds")
        udp_socket.settimeout(None)
        # Ask user for the file save location
        file_save_location = input("Enter the location where to save the file: ")
        if not os.path.exists(file_save_location):
            os.makedirs(file_save_location)  #make sure the directory exists

        file_save_path = os.path.join(file_save_location, file_name)

        # Write the collected fragments to the file
        with open(file_save_path, 'wb') as f:
            for seq_num in sorted(file_fragments.keys()):  # Iterate over the sorted keys (sequence numbers)
                fragment = file_fragments[seq_num]  # Get the fragment data
                f.write(fragment)  # Write the fragment data to the file

        print(f"File saved successfully at {file_save_path} and has size {len(file_fragments)}")
        # reempties the file_fragments
        file_fragments = {}
        custom_flags = END | NAME | ACK
        kal_back_header = create_header(seq_num=0, window_size=1, flags=custom_flags, data_length=0, checksum=0)
        udp_socket.sendto(kal_back_header, addr)
        print("renewing kal")
        kal_counter = 0
        my_timer = time.time()
        stop = True
        return

    #if we are receiving a file fragment
    if flags == FILE:
        stop = False
        if checksum == calculate_checksum(payload):
            print(f"Received fragment {seq_num}, adding to file fragments")
            # print(f"Type of payload for fragment {seq_num}: {type(payload)}")
            file_fragments[seq_num] = payload  # Store the fragment by its sequence number
            # Send acknowledgment for the received fragment
            response_flags = FILE | ACK
            response_header = create_header(seq_num, window_size=1, flags=response_flags, data_length=0, checksum=0)
            udp_socket.sendto(response_header, addr)
            print(f"Sent ACK for fragment {seq_num}")
        else:
            print(f"Received fragment {seq_num}, but checksum mismatch -> resending...")
            response_flags = FILE | ERROR
            response_header = create_header(seq_num, window_size=1, flags=response_flags, data_length=0, checksum=0)
            udp_socket.sendto(response_header, addr)



def receive_messages():
    global connected
    global kal_counter
    global running
    global prev_data
    global file_place
    global file_fragments
    global file_name
    global stop
    global my_timer
    global switcher
    global msg
    global adr
    global file_timer
    global file_timer_switch
    global total_time
    global bad
    global all_frag
    global smallest
    global biggest

    print(f"Listening for messages on port {receive_port}...")

    while running:
        try:
            message, addr = udp_socket.recvfrom(2048)

            #ensure message has enough bytes for the header (11 bytes)
            if len(message) < 11:
                print("Received an incomplete packet; skipping...")
                continue

            #unpack the 11-byte header
            seq_num, window_size, flags, data_length, checksum = struct.unpack('!IHBHH', message[:11])
            payload = message[11:]

            #handshake logic using SYN and SYN-ACK (2 way handshake)
            if flags == SYN and not connected:
                print("Received SYN, sending SYN-ACK response")
                response_flags = SYN | ACK  # Set flags to 00000011 (SYN + ACK)
                response_header = create_header(seq_num, window_size, response_flags, 0, 0)
                udp_socket.sendto(response_header, addr)
                connected = True  #set connected to True for the receiver of SYN
                my_timer = time.time()
            elif flags == (SYN | ACK) and not connected:
                print("Received SYN-ACK, connection is now established")
                connected = True  #set connected to True for the sender who initiated handshake
                my_timer = time.time()
            elif flags == KAL:
                # print("Received KAL, sending KAL-ACK response")
                kal_counter = 0
                my_timer = time.time()  # reset
            elif flags == NAME:
                file_name = payload.decode()
            elif flags == FILE:
                udp_socket.settimeout(20)
                if file_timer_switch == 0:
                    file_timer_switch = 1
                    total_time = time.time()
                receive_file(seq_num, flags, data_length, checksum, payload, addr)
            elif flags == (FILE | ACK):
                print("recieved file ack")
                msg = message
                switcher = 1
            elif flags == (FILE | ERROR):
                msg = message
                switcher = 1
            elif flags == (FILE | END):
                receive_file(seq_num, flags, data_length, checksum, payload, addr)
                file_timer_switch = 0
            elif flags == (END | NAME | ACK):
                print("renewing kal")
                kal_counter = 0
                my_timer = time.time()
                stop = True
            elif flags == END:
                print("Received end communication request. Ending connection.")
                stop = False
                running = False
                break

            elif flags == (MESSAGE | END) and payload:
                if checksum == calculate_checksum(payload):
                    print(f"Peer {addr}: {payload.decode()}")
                    response_flags = MESSAGE | NAME
                    response_header = create_header(seq_num, window_size, response_flags, 0, 0)
                    udp_socket.sendto(response_header, addr)
                else:
                    print("Checksum mismatch detected")
                    response_flags = MESSAGE | NAME | ERROR
                    response_header = create_header(seq_num, window_size, response_flags, 0, 0)
                    udp_socket.sendto(response_header, addr)

            elif flags == (MESSAGE | NAME):
                print("succesfully sent")
                all_frag += 1
                print("štatistika -> ")
                print("počet všetkých fragmentov -> ", all_frag)
                print("počet zlých fragmentov -> ", bad)
                bad = 0
                all_frag = 0
                print("najmensi frag ->", smallest)
                print("najvacsi frag ->", biggest)
                smallest = 0
                biggest = 0


            elif flags == (MESSAGE | NAME | ERROR):
                print("Received error notification from peer")
                checksum = calculate_checksum(prev_data)
                response_flags = MESSAGE | END
                header = create_header(seq_num=0, window_size=1, flags=response_flags, data_length=len(prev_data),
                                       checksum=checksum)
                packet = header + prev_data
                udp_socket.sendto(packet, addr)
                print("Resent corrected message")
                bad += 1
                all_frag += 1

            elif flags == MESSAGE:
                udp_socket.settimeout(20)
                if file_timer_switch == 0:
                    file_timer_switch = 1
                    total_time = time.time()
                receive_frag_messege(seq_num, flags, data_length, checksum, payload, addr)

            elif flags == (MESSAGE | ERROR):
                msg = message
                switcher = 2

            elif flags == (MESSAGE | ACK):
                msg = message
                switcher = 2
            elif flags == (MESSAGE | ACK | END):
                receive_frag_messege(seq_num, flags, data_length, checksum, payload, addr)
                file_timer_switch = 0

        except ConnectionResetError:
            continue
        except OSError:
            print("ending connection")
            running = False
            return

    udp_socket.close()
    running = False


def send_messages():
    global connected
    global running
    global prev_data
    global fragment_size
    global file_place
    global err
    global stop
    global mess_frag_size
    peer_addr = (guest, send_port)  #set destination address
    print("enter handshake to start")
    while running:
        message = input()
        if not running:
            break
        #initiate handshake if not connected
        if message.lower() == 'handshake' and not connected:
            print("Initiating handshake...")
            initiate_handshake(peer_addr, seq_num=0, window_size=1)
            time.sleep(1)  #allow time for the SYN-ACK to be processed by receive_messages
        elif message.lower() == 'exit' and connected:
            #send end communication packet
            end_header = create_header(seq_num=0, window_size=1, flags=END, data_length=0, checksum=0)
            udp_socket.sendto(end_header, peer_addr)
            print("Sent end communication signal")
            stop = False
            break
        elif message.lower() == 'mess_error' and connected:
            err = 1
            print("the messege will be tempered with")
        elif message.lower() == 'file_error':
            err = 1
            print("the file will be tempered with")
        elif message.lower() == 'frag_size':
            frag_size = int(input("Enter fragment size: "))
            while frag_size > 1489:  # 1500 -> maximálna veľkosť fragmentu - header_size čo je u mňa 11 B
                frag_size = int(input("Enter fragment size: "))
            fragment_size = frag_size
            print(f"Fragment size is set to {fragment_size}")
        elif message.lower() == 'file_loc' and connected:
            file_place = input("Enter file location: ")
            f_name = os.path.basename(file_place)
            data = f_name.encode()
            header = create_header(seq_num=0, window_size=1, flags=NAME, data_length=len(data), checksum=0)
            packet = header + data
            udp_socket.sendto(packet, peer_addr)

        elif message.lower() == 'file' and connected:
            if fragment_size == 0:
                print("No fragment size given")
            elif file_place == "":
                print("No file location given")
            else:
                print("starting file transfer")
                send_file(peer_addr)

        elif message.lower() == 'mess_frag':
            message_frag_size = int(input("Enter fragment size: "))
            while message_frag_size > 1489:  # 1500 -> maximálna veľkosť fragmentu - header_size čo je u mňa 11 B
                message_frag_size = int(input("Enter fragment size: "))
            mess_frag_size = message_frag_size
        elif message.lower() == 'guide':
            guide()
        elif connected:
            data = message.encode()
            prev_data = data
            send_frag_mess(data, peer_addr)
        else:
            print("Connection not established. Type 'handshake' to initiate.")

    udp_socket.close()
    running = False


#start threads for sending and receiving
receive_thread = threading.Thread(target=receive_messages)
send_thread = threading.Thread(target=send_messages)
kal_thread = threading.Thread(target=keep_alive)

#start threads
receive_thread.start()
send_thread.start()
kal_thread.start()

receive_thread.join()
send_thread.join()
kal_thread.join()

print("Communication ended.")