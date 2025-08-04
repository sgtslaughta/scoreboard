#!/usr/bin/env python3
"""
Test client to generate test data for the scoreboard system.
Creates 50 different labs with multiple players and random scores.
"""

import socket
import time
import random


def send_score(server_host, server_port, player_name, lab_name, score):
    """Send a single score to the scoreboard server."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_host, server_port))

        # Receive welcome message
        client_socket.recv(1024)  # Welcome message (not used)

        # Send score (no padding required)
        test_message = f"{player_name},{lab_name},{score}\n"
        client_socket.send(test_message.encode("ascii"))

        # Receive response
        client_socket.recv(4096)  # Response (not used)

        client_socket.close()
        return True

    except (ConnectionError, OSError) as e:
        print(f"Error sending score: {e}")
        return False


def generate_test_data(
    server_host="localhost",
    server_port=8080,
):
    """Generate comprehensive test data for the scoreboard."""

    first_names = [
        "Alice",
        "Bob",
        "Charlie",
        "Diana",
        "Eve",
        "Frank",
        "Grace",
        "Henry",
        "Ivy",
        "Jack",
        "Kate",
        "Leo",
        "Maya",
        "Noah",
        "Olivia",
        "Paul",
        "Quinn",
        "Ruby",
        "Sam",
        "Tina",
        "Uma",
        "Victor",
        "Wendy",
        "Xander",
        "Yara",
        "Zoe",
        "Adam",
        "Bella",
        "Carl",
        "Delia",
        "Ethan",
        "Fiona",
        "George",
        "Hannah",
        "Ian",
        "Julia",
        "Kevin",
        "Luna",
        "Max",
        "Nina",
        "Oscar",
        "Penny",
        "Quincy",
        "Rachel",
        "Steve",
        "Tessa",
        "Ulrich",
        "Vera",
        "Will",
        "Ximena",
        "York",
        "Zara",
    ]

    challenge_names = [
        "RSA_Baby",
        "AES_Master",
        "Hash_Cracker",
        "DiffieHell",
        "ECC_Curve",
        "SQLi_Basic",
        "XSS_Hunter",
        "CSRF_Token",
        "JWT_Forge",
        "LFI_Path",
        "BuffOver",
        "ROP_Chain",
        "Format_Str",
        "HeapSpray",
        "Stack_Canary",
        "RE_Basics",
        "Unpack_Me",
        "Anti_Debug",
        "VM_Detect",
        "Code_Cave",
        "Zip_Bomb",
        "QR_Hidden",
        "Audio_Spec",
        "Polyglot",
        "Base64_Nest",
        "LSB_Hide",
        "Pixel_Art",
        "PNG_Secret",
        "JPEG_Meta",
        "GIF_Frame",
        "Google_Fu",
        "LinkedIn",
        "Username",
        "Email_Hunt",
        "Geo_Photo",
        "Disk_Image",
        "Memory_Dump",
        "Network_Cap",
        "Log_Analysis",
        "File_Carv",
        "Blind_SQL",
        "XXE_Parse",
        "SSTI_Jinja",
        "Deserialization",
        "Race_Cond",
        "Use_After_Free",
        "Double_Free",
        "Integer_Over",
        "Path_Traverse",
        "Command_Inj",
    ]

    labs = challenge_names.copy()

    print(f"Generating test data for {len(labs)} labs...")
    print("Sample lab names:", labs[:10])

    total_entries = 0

    for lab_name in labs:
        num_players = random.randint(3, 15)
        lab_players = random.sample(first_names, min(num_players, len(first_names)))

        print(f"Creating {num_players} entries for {lab_name}...")

        for player_name in lab_players:
            base_score = random.randint(1, 300)

            if random.random() < 0.15:  # 15% chance of tie
                tie_scores = [10, 25, 50, 100, 150, 200]
                base_score = random.choice(tie_scores)

            if send_score(server_host, server_port, player_name, lab_name, base_score):
                total_entries += 1

            time.sleep(0.01)

    print("\nTest data generation complete!")
    print(f"Created {total_entries} total entries across {len(labs)} labs")
    return total_entries


def test_single_score(server_host="localhost", server_port=8080):
    """Test sending a single score (original functionality)."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_host, server_port))

        welcome = client_socket.recv(1024)
        print(
            f"Received welcome ({len(welcome)} bytes): {welcome.decode('ascii').strip()}"
        )

        test_message = "TestUser,Demo,42\n"
        client_socket.send(test_message.encode("ascii"))
        print(f"Sent message ({len(test_message)} bytes): {test_message.strip()}")

        # Receive response
        response = client_socket.recv(4096)
        print(f"Received response:\n{response.decode('ascii')}")

        client_socket.close()
        print("Single score test completed successfully!")
        return True

    except (ConnectionError, OSError) as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--generate":
            # Generate comprehensive test data
            host = sys.argv[2] if len(sys.argv) > 2 else "localhost"
            port = int(sys.argv[3]) if len(sys.argv) > 3 else 8080
            print("Starting test data generation...")
            generate_test_data(host, port)
        elif sys.argv[1] in ["--help", "-h"]:
            print("Scoreboard Test Client")
            print("=" * 30)
            print("")
            print("Usage:")
            print("  python test_client.py                    # Send single test score")
            print(
                "  python test_client.py --generate         # Generate 50 labs with random data"
            )
            print(
                "  python test_client.py --generate HOST    # Generate data to specific host"
            )
            print(
                "  python test_client.py --generate HOST PORT # Generate data to host:port"
            )
            print("")
            print("Examples:")
            print("  python test_client.py --generate localhost 8080")
            print("  python test_client.py --generate 192.168.1.100")
            print("")
            print("Test Data Generation Features:")
            print("  - Creates 50 different realistic CTF challenges")
            print(
                "  - 8 categories: Crypto, Web, Pwn, Rev, Misc, Stego, Osint, Forensics"
            )
            print(
                "  - Challenge names: Realistic CTF names (e.g., RSA_Baby, SQLi_Basic, BuffOver)"
            )
            print("  - 3-15 random players per challenge")
            print("  - Realistic scoring (1-300 points, lower is better)")
            print("  - 15% chance of tied scores for testing tie functionality")
            print("  - Over 50 different player names")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        # Run single score test (original behavior)
        test_single_score()
