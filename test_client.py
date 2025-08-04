#!/usr/bin/env python3
"""
Test client to generate test data for the scoreboard system.
Creates 50 different labs with multiple players and random scores.
"""

import socket
import time
import random


def send_score(host, port, player_name, lab_name, score):
    """Send a single score to the scoreboard server."""
    try:
        # Connect to server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))

        # Receive welcome message (exactly 512 bytes)
        welcome = client_socket.recv(512)

        # Send score (pad to 512 bytes as per protocol)
        test_message = f"{player_name},{lab_name},{score}"
        padded_message = test_message.encode("ascii").ljust(512, b"\x00")
        client_socket.send(padded_message)

        # Receive response
        response = client_socket.recv(4096)

        client_socket.close()
        return True

    except Exception as e:
        print(f"Error sending score: {e}")
        return False


def generate_test_data(host="localhost", port=8080):
    """Generate comprehensive test data for the scoreboard."""

    # Random names for players
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

    # Generate 50 different lab names (max 4 characters as per server validation)
    lab_prefixes = ["C", "W", "P", "R", "M", "S", "O", "F"]  # Short prefixes for categories
    lab_categories = ["Crypto", "Web", "Pwn", "Rev", "Misc", "Stego", "Osint", "Forensics"]
    
    labs = []
    used_names = set()
    
    # Generate unique 4-character lab names
    for i in range(50):
        attempts = 0
        while attempts < 100:  # Avoid infinite loop
            prefix = random.choice(lab_prefixes)
            number = random.randint(1, 999)
            lab_name = f"{prefix}{number}"
            
            # Ensure it's max 4 characters and unique
            if len(lab_name) <= 4 and lab_name not in used_names:
                labs.append(lab_name)
                used_names.add(lab_name)
                break
            attempts += 1
        
        # Fallback if we can't generate unique name
        if len(labs) <= i:
            lab_name = f"L{i+1}"
            labs.append(lab_name)

    print(f"Generating test data for {len(labs)} labs...")
    print("Sample lab names:", labs[:10])

    total_entries = 0

    # For each lab, create 3-15 random players with scores
    for lab_name in labs:
        num_players = random.randint(3, 15)  # Random number of players per lab
        lab_players = random.sample(first_names, min(num_players, len(first_names)))

        print(f"Creating {num_players} entries for {lab_name}...")

        for player_name in lab_players:
            # Generate score (lower is better, range 1-300)
            base_score = random.randint(1, 300)

            # Add some chance for ties
            if random.random() < 0.15:  # 15% chance of tie
                tie_scores = [10, 25, 50, 100, 150, 200]
                base_score = random.choice(tie_scores)

            # Send the score
            if send_score(host, port, player_name, lab_name, base_score):
                total_entries += 1

            # Small delay to avoid overwhelming the server
            time.sleep(0.01)

    print(f"\nTest data generation complete!")
    print(f"Created {total_entries} total entries across {len(labs)} labs")
    return total_entries


def test_single_score(host="localhost", port=8080):
    """Test sending a single score (original functionality)."""
    try:
        # Connect to server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))

        # Receive welcome message (exactly 512 bytes)
        welcome = client_socket.recv(512)
        print(
            f"Received welcome ({len(welcome)} bytes): {welcome.decode('ascii').strip()}"
        )

        # Send test score (pad to 512 bytes as per protocol)
        test_message = "TestUser,Demo,42"
        padded_message = test_message.encode("ascii").ljust(512, b"\x00")
        client_socket.send(padded_message)
        print(f"Sent message ({len(padded_message)} bytes): {test_message}")

        # Receive response
        response = client_socket.recv(4096)
        print(f"Received response:\n{response.decode('ascii')}")

        client_socket.close()
        print("Single score test completed successfully!")
        return True

    except Exception as e:
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
            print("  - Creates 50 different CTF-style challenges")
            print("  - 8 categories: C(rypto), W(eb), P(wn), R(ev), M(isc), S(tego), O(sint), F(orensics)")
            print("  - Challenge names: 4 chars max (e.g., C123, W45, P7)")
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
