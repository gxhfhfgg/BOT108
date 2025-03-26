import logging
import subprocess
import sys
import os
import re
import time
import concurrent.futures
import random
import discord
from discord.ext import commands, tasks
import docker
import asyncio
from discord import app_commands
import requests

# Set Your Bot Token gay
TOKEN = 'YOUR_BOT_TOKEN'
RAM_LIMIT = '6g' #Set Your Own Ram How Much You Want To Give Your Users
SERVER_LIMIT = 2 #you can change it!
database_file = 'database.txt'

intents = discord.Intents.default()
intents.messages = False
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)
client = docker.from_env()

whitelist_ids = {"1128161197766746213"}  # Replace with actual user IDs

# Utility Functions
def add_to_database(userid, container_name, ssh_command):
    with open(database_file, 'a') as f:
        f.write(f"{userid}|{container_name}|{ssh_command}\n")

def remove_from_database(ssh_command):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if ssh_command not in line:
                f.write(line)

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

def count_user_servers(userid):
    return len(get_user_servers(userid))

def get_container_id_from_database(userid, container_name):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(userid) and container_name in line:
                return line.split('|')[1]
    return None

def generate_random_port():
    return random.randint(1025, 65535)

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
    return None



# In-memory database for user credits
user_credits = {}

# Cuty.io API key (Your account key)
API_KEY = 'ebe681f9e37ef61fcfd756396'

# Slash command: earnCredit
@bot.tree.command(name="earncredit", description="Generate a URL to shorten and earn credits.")
async def earncredit(interaction: discord.Interaction):
    print("Received request to shorten URL")
    user_id = interaction.user.id

    # Define a default URL to shorten
    default_url = "https://cuty.io/e58WUzLMmE3S"  # Change this as needed

    # Make a request to Cuty.io API to shorten the default URL
    api_url = f"https://cutt.ly/api/api.php?key={API_KEY}&short={default_url}"
    print(f"Making API call to: {api_url}")
    response = requests.get(api_url).json()
    print(f"API response: {response}")

    # Check if the URL was successfully shortened
    if response['url']['status'] == 7:
        shortened_url = response['url']['shortLink']
        credits_earned = 1  # Update to 1 credit for each shortening

        # Add credits to user
        user_credits[user_id] = user_credits.get(user_id, 0) + credits_earned

        await interaction.response.send_message(f"Success! Here's your shortened URL: {shortened_url}. You earned {credits_earned} credit!")
    else:
        # Handle API error messages
        error_message = response['url'].get('title', 'Failed to generate a shortened URL. Please try again.')
        await interaction.response.send_message(error_message)

# Slash command: bal
@bot.tree.command(name="bal", description="Check your credit balance.")
async def bal(interaction: discord.Interaction):
    user_id = interaction.user.id
    credits = user_credits.get(user_id, 0)
    await interaction.response.send_message(f"You have {credits} credits.")
#portnew
@bot.tree.command(name="port-forward-new", description="Set up port forwarding for a container using localhost.run.")
@app_commands.describe(container_name="The name of the container", container_port="The port inside the container to forward")
async def port_forward_win(interaction: discord.Interaction, container_name: str, container_port: int):
    await interaction.response.defer()  # Allow time for execution
    try:
        # Use localhost.run for port forwarding
        command = f"docker exec -it {container_name} ssh -R 80:localhost:{container_port} ssh.localhost.run"
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()

        if stdout:
            output = stdout.decode().strip()
            await interaction.followup.send(embed=discord.Embed(
                description=f"### Port Forwarding Successful:\n{output}",
                color=0x00ff00
            ))
        if stderr:
            error = stderr.decode().strip()
            await interaction.followup.send(embed=discord.Embed(
                description=f"### Error in Port Forwarding:\n{error}",
                color=0xff0000
            ))
    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(
            description=f"### Failed to set up port forwarding: {str(e)}",
            color=0xff0000
        ))

# Node Status Command
def get_node_status():
    try:
        containers = client.containers.list(all=True)
        container_status = "\n".join([f"{container.name} - {container.status}" for container in containers]) or "No containers running."

        # Get system-wide memory usage using `os` module
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        mem_total = int(re.search(r'MemTotal:\s+(\d+)', meminfo).group(1)) / 1024  # Convert to MB
        mem_free = int(re.search(r'MemFree:\s+(\d+)', meminfo).group(1)) / 1024  # Convert to MB
        mem_available = int(re.search(r'MemAvailable:\s+(\d+)', meminfo).group(1)) / 1024  # Convert to MB

        memory_used = mem_total - mem_available
        memory_percentage = (memory_used / mem_total) * 100 if mem_total else 0

        node_info = {
            "containers": container_status,
            "memory_total": mem_total,
            "memory_used": memory_used,
            "memory_percentage": memory_percentage
        }
        return node_info
    except Exception as e:
        return str(e)

@bot.tree.command(name="node", description="Show the current status of the VPS node.")
async def node_status(interaction: discord.Interaction):
    try:
        node_info = get_node_status()

        if isinstance(node_info, str):  # If there's an error
            await interaction.response.send_message(embed=discord.Embed(description=f"### Error fetching node status: {node_info}", color=0xff0000))
            return

        # Format the status message
        embed = discord.Embed(title="VPS Node1 Status", color=0x00ff00)
        embed.add_field(name="Containers", value=node_info["containers"], inline=False)
        embed.add_field(name="Memory Usage", value=f"{node_info['memory_used']:.2f} / {node_info['memory_total']:.2f} MB ({node_info['memory_percentage']:.2f}%)", inline=False)

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"### Failed to fetch node status: {str(e)}", color=0xff0000))


@bot.tree.command(name="renew", description="Renew a VPS for 8 days using 2 credits.")
@app_commands.describe(vps_id="ID of the VPS to renew")
async def renew(interaction: discord.Interaction, vps_id: str):
    user_id = str(interaction.user.id)
    credits = user_credits.get(user_id, 0)

    # Check if user has enough credits
    if credits < 2:
        await interaction.response.send_message(embed=discord.Embed(
            description="You don't have enough credits to renew the VPS. You need 2 credits.",
            color=0xff0000))
        return

    # Get VPS from the database (check if VPS exists for the user)
    container_id = get_container_id_from_database(user_id, vps_id)
    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(
            description=f"VPS with ID {vps_id} not found.",
            color=0xff0000))
        return

    # Deduct credits
    user_credits[user_id] -= 2

    # Renew VPS: Add 8 days to the current expiry
    renewal_date = datetime.now() + timedelta(days=8)
    vps_renewals[vps_id] = renewal_date

    # You may also want to log this in a persistent database, not just in memory

    await interaction.response.send_message(embed=discord.Embed(
        description=f"VPS {vps_id} has been renewed for 8 days. New expiry date: {renewal_date.strftime('%Y-%m-%d')}. "
                    f"You now have {user_credits[user_id]} credits remaining.",
        color=0x00ff00))


# Remove Everything Task
async def remove_everything_task(interaction: discord.Interaction):
    await interaction.channel.send("### Node is full. Resetting all user instances...")
    try:
        subprocess.run("docker rm -f $(sudo docker ps -a -q)", shell=True, check=True)
        os.remove(database_file)
        subprocess.run("pkill pytho*", shell=True, check=True)
        await interaction.channel.send("### All instances and data have been reset.")
    except Exception as e:
        await interaction.channel.send(f"### Failed to reset instances: {str(e)}")

# KillVPS Command (Admin only)
@bot.tree.command(name="killvps", description="Kill all user VPS instances. Admin only.")
async def kill_vps(interaction: discord.Interaction):
    userid = str(interaction.user.id)
    if userid not in whitelist_ids:
        await interaction.response.send_message(embed=discord.Embed(description="You do not have permission to use this command.", color=0xff0000))
        return

    await remove_everything_task(interaction)
    await interaction.response.send_message(embed=discord.Embed(description="### All user VPS instances have been terminated.", color=0x00ff00))

def add_to_database(userid, container_name, ssh_command):
    with open(database_file, 'a') as f:
        f.write(f"{userid}|{container_name}|{ssh_command}\n")

def remove_from_database(ssh_command):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if ssh_command not in line:
                f.write(line)

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
    return None

whitelist_ids = {"1128161197766746213"}  # Replace with actual user IDs

@bot.tree.command(name="remove-everything", description="Removes all data and containers")
async def remove_everything(interaction: discord.Interaction):
    userid = str(interaction.user.id)
    if userid not in whitelist_ids:
        await interaction.response.send_message(embed=discord.Embed(description="You do not have permission to use this command.", color=0xff0000))
        return

    # Remove all Docker containers
    try:
        subprocess.run("docker rm -f $(sudo docker ps -a -q)", shell=True, check=True)
        await interaction.response.send_message(embed=discord.Embed(description="All Docker containers have been removed.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description="Failed to remove Docker containers.", color=0xff0000))

    # Remove database and port files
    try:
        os.remove(database_file)
        os.remove(port_db_file)
        await interaction.response.send_message(embed=discord.Embed(description="Database and port files have been cleared. Service has been restarted. Please start the bot in the shell", color=0x00ff00))
        subprocess.run("pkill pytho*", shell=True, check=True)
    except Exception as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Failed to clear database or restart service: {str(e)}", color=0xff0000))

#@tasks.loop(seconds=5)
#async def change_status():
#    try:
#        if os.path.exists(database_file):
#            with open(database_file, 'r') as f:
#                lines = f.readlines()
#                instance_count = len(lines)
#        else:
#            instance_count = 0
#
#        status = f"with {instance_count} Cloud Instances"
#        await bot.change_presence(activity=discord.Game(name=status))
#    except Exception as e:
#        print(f"Failed to update status: {e}")

def get_ssh_command_from_database(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                return line.split('|')[2]
    return None

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

def count_user_servers(userid):
    return len(get_user_servers(userid))

def get_container_id_from_database(userid):
    servers = get_user_servers(userid)
    if servers:
        return servers[0].split('|')[1]
    return None

@bot.event
async def on_ready():
    #change_status.start()
    print(f'Bot is ready. Logged in as {bot.user}')
    await bot.tree.sync()

async def regen_ssh_command(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No active instance found for your user.", color=0xff0000))
        return

    try:
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error executing tmate in Docker container: {e}", color=0xff0000))
        return

    ssh_session_line = await capture_ssh_session_line(exec_cmd)
    if ssh_session_line:
        await interaction.user.send(embed=discord.Embed(description=f"### New SSH Session Command: ```{ssh_session_line}```", color=0x00ff00))
        await interaction.response.send_message(embed=discord.Embed(description="### New SSH session generated. Check your DMs for details.", color=0x00ff00))
    else:
        await interaction.response.send_message(embed=discord.Embed(description="### Failed to generate new SSH session.", color=0xff0000))

async def start_server(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No instance found for your user.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "start", container_id], check=True)
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        ssh_session_line = await capture_ssh_session_line(exec_cmd)
        if ssh_session_line:
            await interaction.user.send(embed=discord.Embed(description=f"### Instance Started\nSSH Session Command: ```{ssh_session_line}```", color=0x00ff00))
            await interaction.response.send_message(embed=discord.Embed(description="### Instance started successfully. Check your DMs for details.", color=0x00ff00))
        else:
            await interaction.response.send_message(embed=discord.Embed(description="### Instance started, but failed to get SSH session line.", color=0xff0000))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error starting instance: {e}", color=0xff0000))

async def stop_server(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No instance found for your user.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "stop", container_id], check=True)
        await interaction.response.send_message(embed=discord.Embed(description="### Instance stopped successfully.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"### Error stopping instance: {e}", color=0xff0000))

async def restart_server(interaction: discord.Interaction, container_name: str):
#    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(userid, container_name)

    if not container_id:
        await interaction.response.send_message(embed=discord.Embed(description="### No instance found for your user.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "restart", container_id], check=True)
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_id, "tmate", "-F",
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        ssh_session_line = await capture_ssh_session_line(exec_cmd)
        if ssh_session_line:
            await interaction.user.send(embed=discord.Embed(description=f"### Instance Restarted\nSSH Session Command: ```{ssh_session_line}```\nOS: Ubuntu 22.04", color=0x00ff00))
            await interaction.response.send_message(embed=discord.Embed(description="### Instance restarted successfully. Check your DMs for details.", color=0x00ff00))
        else:
            await interaction.response.send_message(embed=discord.Embed(description="### Instance restarted, but failed to get SSH session line.", color=0xff0000))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"Error restarting instance: {e}", color=0xff0000))

def get_container_id_from_database(userid, container_name):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(userid) and container_name in line:
                return line.split('|')[1]
    return None

def generate_random_port():
    return random.randint(1025, 65535)

async def create_server_task(interaction: discord.Interaction, ram: int, cores: int):
    await interaction.response.send_message(embed=discord.Embed(
        description=f"### 🚀 Creating Instance ({ram}GB RAM, {cores} Cores)... Please wait.",
        color=0x00ff00
    ))

    userid = str(interaction.user.id)
    is_admin = userid in whitelist_ids  # ✅ Check if the user is an admin

    # 🛑 **Enforce RAM & CPU Limits**
    if not is_admin:
        ram, cores = 4, 2  # Normal users always get **4GB RAM, 2 Cores**
    else:
        if ram < 1 or ram > 100:
            await interaction.followup.send(embed=discord.Embed(description="❌ **Error:** RAM must be between **1GB and 100GB**.", color=0xff0000))
            return
        if cores < 1 or cores > 100:
            await interaction.followup.send(embed=discord.Embed(description="❌ **Error:** CPU cores must be between **1 and 100**.", color=0xff0000))
            return

    if count_user_servers(userid) >= SERVER_LIMIT:
        await interaction.followup.send(embed=discord.Embed(description="❌ **Error:** Instance Limit Reached!", color=0xff0000))
        return

    image = "ubuntu-22.04-with-tmate"
    ram_str = f"{ram}g"  # ✅ **Ensure correct RAM format**
    container_name = f"vps_{userid}_{random.randint(1000, 9999)}"  # ✅ **Generate a unique VPS name**

    # ✅ **Remove old containers with the same name (if any)**
    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        # ✅ **Run Docker Container with Correct RAM & CPU**
        container_id = subprocess.check_output([
            "docker", "run", "-itd", "--privileged",
            "--hostname", "nxh-i9",
            "--memory", ram_str, "--cpus", str(cores),
            "--name", container_name, "--cap-add=ALL", image
        ]).strip().decode('utf-8')

    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(description=f"❌ **Error creating Docker container:** {e}", color=0xff0000))
        return

    try:
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(description=f"❌ **Error executing tmate in Docker container:** {e}", color=0xff0000))
        subprocess.run(["docker", "rm", "-f", container_id])  # 🛑 **Remove broken instance**
        return

    ssh_session_line = await capture_ssh_session_line(exec_cmd)
    if ssh_session_line:
        add_to_database(userid, f"{container_id}|{ram}GB RAM - {cores} Cores - Premium", ssh_session_line)

        await interaction.user.send(embed=discord.Embed(description=f"✅ **Instance Created**\n"
                                                                    f"SSH: ```{ssh_session_line}```\n"
                                                                    f"OS: Ubuntu 22.04\n"
                                                                    f"RAM: **{ram}GB**\n"
                                                                    f"Cores: **{cores}**",
                                                        color=0x00ff00))
        await interaction.followup.send(embed=discord.Embed(description="✅ **Instance created successfully. Check your DMs for details.**", color=0x00ff00))
    else:
        await interaction.followup.send(embed=discord.Embed(description="❌ **Error:** Instance creation took too long.", color=0xff0000))
        subprocess.run(["docker", "rm", "-f", container_id])  # 🛑 **Remove broken instance**

# Define admin user IDs
@bot.tree.command(name="deploy", description="Creates a new VPS instance with specific RAM & CPU configurations.")
@app_commands.describe(ram="Amount of RAM (e.g., 4G, 8G, 16G)", cpu="Number of CPU cores (e.g., 1, 2, 3, 5)")
async def deploy(interaction: discord.Interaction, ram: str, cpu: int):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    container_name = f"vps_{user_id}"
    admin_ids = {"1119657947434332211", "1085944828883369984"}

    # Allowed RAM & CPU Combinations
    allowed_combinations = {
        "8G": 1,
        "4G": 2,
        "3G": 3,
        "16G": 5,
        "5G": 3
    }

    # Admins can generate unlimited VPS, normal users can only have 1
    if user_id not in admin_ids and count_user_servers(user_id) >= 1:
        embed = discord.Embed(
            title="🚫 VPS Limit Reached!",
            description="Normal members can only create **1 VPS (4GB RAM, 2 Cores).**",
            color=0xff0000  # Red for error
        )
        embed.set_footer(text="Delete your existing VPS before creating a new one.")
        await interaction.followup.send(embed=embed)
        return

    # Validate RAM & CPU
    ram_value = ram.upper().replace("GB", "G")
    if ram_value not in allowed_combinations or allowed_combinations[ram_value] != cpu:
        embed = discord.Embed(
            title="🚫 Invalid RAM & CPU Configuration!",
            description="Please select a valid RAM & CPU combination:",
            color=0xff0000  # Red for error
        )
        embed.add_field(name="✅ Allowed Configurations:", value=(
            "🔹 **8GB RAM → 1 Core**\n"
            "🔹 **4GB RAM → 2 Cores**\n"
            "🔹 **3GB RAM → 3 Cores**\n"
            "🔹 **16GB RAM → 5 Cores**\n"
            "🔹 **5GB RAM → 3 Cores**"
        ), inline=False)
        embed.set_footer(text="Please try again with a valid configuration.")
        await interaction.followup.send(embed=embed)
        return

    # Remove existing container if it exists
    existing_containers = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"],
                                         capture_output=True, text=True).stdout.split("\n")
    if container_name in existing_containers:
        subprocess.run(["docker", "rm", "-f", container_name])

    try:
        # Run Docker Container
        container_id = subprocess.check_output([
            "docker", "run", "-itd", "--privileged",
            "--memory", ram_value, "--cpus", str(cpu),
            "--hostname", "nxh-i7", "--name", container_name,
            "--cap-add=ALL", "ubuntu-22.04-with-tmate"
        ]).strip().decode('utf-8')

        # Capture SSH session
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        ssh_session_line = await capture_ssh_session_line(exec_cmd)

        if ssh_session_line:
            add_to_database(user_id, container_id, ssh_session_line)

            # **Cool Success Embed**
            embed = discord.Embed(
                title="🎉 VPS Successfully Deployed!",
                description="Your instance has been created with the following specifications:",
                color=0x00ff00  # Green for success
            )
            embed.add_field(name="🖥️ SSH Command:", value=f"```{ssh_session_line}```", inline=False)
            embed.add_field(name="🔹 RAM:", value=f"**{ram}**", inline=True)
            embed.add_field(name="🔹 CPU:", value=f"**{cpu} Cores**", inline=True)
            embed.add_field(name="📌 Hostname:", value="**nxh-i7**", inline=False)
            embed.set_footer(text="🚀 Enjoy your new VPS!")

            # Send DM to user with VPS details
            await interaction.user.send(embed=embed)

            # Public confirmation message
            await interaction.followup.send(embed=discord.Embed(
                title="🚀 VPS Created!",
                description="✅ **Your instance is ready!**\n📩 Check your DMs for SSH details.",
                color=0x00ff00
            ))

        else:
            raise Exception("Failed to generate SSH session.")

    except subprocess.CalledProcessError as e:
        embed = discord.Embed(
            title="❌ VPS Creation Failed!",
            description=f"An error occurred while creating your VPS:\n```{e}```",
            color=0xff0000  # Red for error
        )
        embed.set_footer(text="Please contact support if this issue persists.")
        await interaction.followup.send(embed=embed)
@bot.tree.command(name="adminnode", description="Shows all created VPS instances (Admins only).")
async def adminnode(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    admin_ids = {"1119657947434332211", "1085944828883369984"}

    if user_id not in admin_ids:
        embed = discord.Embed(
            title="❌ Access Denied",
            description="This command is for **admins only**.",
            color=0xff0000  # Red for error
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Read VPS instances from the database
    if not os.path.exists("database.txt") or os.stat("database.txt").st_size == 0:
        embed = discord.Embed(
            title="📂 No VPS Instances Found",
            description="There are no active VPS instances.",
            color=0xffcc00  # Yellow for warning
        )
        await interaction.response.send_message(embed=embed)
        return

    with open("database.txt", "r") as f:
        vps_list = f.readlines()

    if not vps_list:
        embed = discord.Embed(
            title="📂 No VPS Instances Found",
            description="There are no active VPS instances.",
            color=0xffcc00  # Yellow for warning
        )
        await interaction.response.send_message(embed=embed)
        return

    # Limit to 100 entries per embed
    max_entries = 100
    vps_entries = []
    
    for line in vps_list[:max_entries]:  # Show only first 100 entries
        user, container_name, ssh_command = line.strip().split("|")
        vps_entries.append(
            f"👤 **User ID:** `{user}`\n"
            f"💾 **RAM:** Unknown\n"
            f"🖥️ **CPU:** Unknown\n"
            f"📜 **Container:** `{container_name}`\n"
            f"🔑 **SSH:** `{ssh_command}`\n"
            "➖➖➖➖➖➖➖➖➖➖"
        )

    embed = discord.Embed(
        title="📜 VPS Instance List",
        description="\n".join(vps_entries) if vps_entries else "No data available.",
        color=0x00ff00  # Green for success
    )
    embed.set_footer(text=f"🚀 Showing first {max_entries} instances. Use /delvps to remove a VPS.")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="delvps", description="Deletes a specific user's VPS (Admins only).")
@app_commands.describe(userid="The Discord User ID of the VPS owner to delete.")
async def delvps(interaction: discord.Interaction, userid: str):
    user_id = str(interaction.user.id)
    admin_ids = {"1119657947434332211", "1085944828883369984"}

    if user_id not in admin_ids:
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Access Denied",
            description="This command is for **admins only**.",
            color=0xff0000
        ), ephemeral=True)
        return

    if not os.path.exists("database.txt"):
        await interaction.response.send_message(embed=discord.Embed(
            title="⚠️ No VPS Found",
            description=f"No VPS exists for user `{userid}`.",
            color=0xffcc00
        ))
        return

    with open("database.txt", "r") as f:
        lines = f.readlines()

    new_lines = []
    deleted_vps = None

    for line in lines:
        if line.startswith(userid):
            deleted_vps = line.strip()
            _, container_name, _ = line.strip().split("|")
            subprocess.run(["docker", "rm", "-f", container_name])  # Remove the VPS container
        else:
            new_lines.append(line)

    with open("database.txt", "w") as f:
        f.writelines(new_lines)

    if deleted_vps:
        await interaction.response.send_message(embed=discord.Embed(
            title="✅ VPS Deleted",
            description=f"Successfully deleted the VPS for user `{userid}`.",
            color=0x00ff00
        ))
    else:
        await interaction.response.send_message(embed=discord.Embed(
            title="⚠️ No VPS Found",
            description=f"No VPS exists for user `{userid}`.",
            color=0xffcc00
        ))
@bot.tree.command(name="sendvps", description="Transfer your VPS to another user.")
@app_commands.describe(userid="The Discord User ID of the recipient.")
async def sendvps(interaction: discord.Interaction, userid: str):
    sender_id = str(interaction.user.id)

    if sender_id == userid:
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Invalid Transfer",
            description="You **cannot** transfer a VPS to yourself!",
            color=0xff0000
        ), ephemeral=True)
        return

    if not os.path.exists("database.txt"):
        await interaction.response.send_message(embed=discord.Embed(
            title="⚠️ No VPS Found",
            description="You don't own any VPS to transfer.",
            color=0xffcc00
        ), ephemeral=True)
        return

    with open("database.txt", "r") as f:
        lines = f.readlines()

    new_lines = []
    transferred_vps = None

    for line in lines:
        if line.startswith(sender_id):
            transferred_vps = line.replace(sender_id, userid, 1)
            new_lines.append(transferred_vps)
        else:
            new_lines.append(line)

    if transferred_vps:
        with open("database.txt", "w") as f:
            f.writelines(new_lines)

        await interaction.response.send_message(embed=discord.Embed(
            title="✅ VPS Transferred",
            description=f"Your VPS has been successfully transferred to <@{userid}>.",
            color=0x00ff00
        ))
    else:
        await interaction.response.send_message(embed=discord.Embed(
            title="⚠️ No VPS Found",
            description="You don't own any VPS to transfer.",
            color=0xffcc00
        ), ephemeral=True)
@bot.tree.command(name="ip4vps", description="Create a real IPv4 VPS (Admins only).")
@app_commands.describe(ram="Amount of RAM (Fixed: 8G)", core="Number of CPU cores (Fixed: 2)", port="Custom SSH Port", dockername="Custom Docker Container Name")
async def ip4vps(interaction: discord.Interaction, ram: str, core: int, port: int, dockername: str):
    admin_ids = {"1119657947434332211", "1085944828883369984"}
    user_id = str(interaction.user.id)

    if user_id not in admin_ids:
        await interaction.response.send_message(embed=discord.Embed(
            title="❌ Access Denied",
            description="Only **admins** can create an IPv4 VPS.",
            color=0xff0000
        ), ephemeral=True)
        return

    await interaction.response.send_message(embed=discord.Embed(
        title="🚀 Deploying IPv4 VPS...",
        description=f"Creating VPS with **{ram} RAM**, **{core} Cores**, **Port {port}**, **Docker Name: {dockername}**...",
        color=0x00ff00
    ))

    ssh_ip = "your-vps-ip"  # Replace with your actual VPS IP

    # Ensure no conflicting containers exist
    subprocess.run(["docker", "rm", "-f", dockername], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        # Create the Docker container with SSH access
        container_id = subprocess.check_output([
            "docker", "run", "-itd", "--privileged",
            "-p", f"{port}:22",  # Expose SSH port
            "--memory", "8G", "--cpus", "2",
            "--hostname", "ipv4-vps",
            "--name", dockername, "--cap-add=ALL",
            "ubuntu:22.04"
        ]).strip().decode('utf-8')

        # Install & start SSH in the container
        subprocess.run(["docker", "exec", dockername, "bash", "-c",
                        "apt update && apt install -y openssh-server && service ssh start && echo 'root:password' | chpasswd"])

        ssh_command = f"ssh root@{ssh_ip} -p {port}"

        # Send DM to admin with VPS details
        await interaction.user.send(embed=discord.Embed(
            title="✅ IPv4 VPS Created!",
            description="Your real IPv4 VPS has been successfully deployed.",
            color=0x00ff00
        ).add_field(name="🖥️ SSH Access:", value=f"```{ssh_command}```", inline=False)
         .add_field(name="🔹 RAM:", value="**8G**", inline=True)
         .add_field(name="🔹 CPU:", value="**2 Cores**", inline=True)
         .add_field(name="📌 Docker Name:", value=f"**{dockername}**", inline=False)
         .set_footer(text="🚀 Use this SSH command to access your VPS."))

        await interaction.followup.send(embed=discord.Embed(
            title="🚀 IPv4 VPS Deployed!",
            description="✅ Your VPS has been created. Check your DMs for SSH details.",
            color=0x00ff00
        ))

    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ VPS Deployment Failed!",
            description=f"An error occurred while creating your VPS:\n```{e}```",
            color=0xff0000
        ))

#@bot.tree.command(name="deploy-debian", description="Creates a new Instance with Debian 12")
#async def deploy_ubuntu(interaction: discord.Interaction):
#    await create_server_task_debian(interaction)

@bot.tree.command(name="regen-ssh", description="Generates a new SSH session for your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def regen_ssh(interaction: discord.Interaction, container_name: str):
    await regen_ssh_command(interaction, container_name)

@bot.tree.command(name="start", description="Starts your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def start(interaction: discord.Interaction, container_name: str):
    await start_server(interaction, container_name)

@bot.tree.command(name="stop", description="Stops your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def stop(interaction: discord.Interaction, container_name: str):
    await stop_server(interaction, container_name)

@bot.tree.command(name="restart", description="Restarts your instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def restart(interaction: discord.Interaction, container_name: str):
    await restart_server(interaction, container_name)

@bot.tree.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list", description="Lists all your Instances")
async def list_servers(interaction: discord.Interaction):
    await interaction.response.defer()
    userid = str(interaction.user.id)
    servers = get_user_servers(userid)
    if servers:
        embed = discord.Embed(title="Your Instances", color=0x00ff00)
        for server in servers:
            _, container_name, _ = server.split('|')
            embed.add_field(name=container_name, value="32GB RAM - Premuim - 4 cores", inline=False)
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(embed=discord.Embed(description="You have no servers.", color=0xff0000))

async def execute_command(command):
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode()

PUBLIC_IP = '138.68.79.95'

async def capture_output(process, keyword):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if keyword in output:
            return output
    return None

@bot.tree.command(name="port-add", description="Adds a port forwarding rule")
@app_commands.describe(container_name="The name of the container", container_port="The port in the container")
async def port_add(interaction: discord.Interaction, container_name: str, container_port: int):
#    await interaction.response.defer()
    await interaction.response.send_message(embed=discord.Embed(description="### Setting up port forwarding. This might take a moment...", color=0x00ff00))

    public_port = generate_random_port()

    # Set up port forwarding inside the container
    command = f"ssh -o StrictHostKeyChecking=no -R {public_port}:localhost:{container_port} serveo.net -N -f"

    try:
        # Run the command in the background using Docker exec
        await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "bash", "-c", command,
            stdout=asyncio.subprocess.DEVNULL,  # No need to capture output
            stderr=asyncio.subprocess.DEVNULL  # No need to capture errors
        )

        # Respond immediately with the port and public IP
        await interaction.followup.send(embed=discord.Embed(description=f"### Port added successfully. Your service is hosted on {PUBLIC_IP}:{public_port}.", color=0x00ff00))

    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(description=f"### An unexpected error occurred: {e}", color=0xff0000))

@bot.tree.command(name="port-http", description="Forward HTTP traffic to your container")
@app_commands.describe(container_name="The name of your container", container_port="The port inside the container to forward")
async def port_forward_website(interaction: discord.Interaction, container_name: str, container_port: int):
 #   await interaction.response.defer()
    try:
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "ssh", "-o StrictHostKeyChecking=no", "-R", f"80:localhost:{container_port}", "serveo.net",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        url_line = await capture_output(exec_cmd, "Forwarding HTTP traffic from")
        if url_line:
            url = url_line.split(" ")[-1]
            await interaction.response.send_message(embed=discord.Embed(description=f"### Website forwarded successfully. Your website is accessible at {url}.", color=0x00ff00))
        else:
            await interaction.response.send_message(embed=discord.Embed(description="### Failed to capture forwarding URL.", color=0xff0000))
    except subprocess.CalledProcessError as e:
        await interaction.response.send_message(embed=discord.Embed(description=f"### Error executing website forwarding: {e}", color=0xff0000))

@bot.tree.command(name="remove", description="Removes an Instance")
@app_commands.describe(container_name="The name/ssh-command of your Instance")
async def remove_server(interaction: discord.Interaction, container_name: str):
    await interaction.response.defer()
    userid = str(interaction.user.id)
    container_id = get_container_id_from_database(userid, container_name)

    if not container_id:
        await interaction.followup.send(embed=discord.Embed(description="### No Instance found for your user with that name.", color=0xff0000))
        return

    try:
        subprocess.run(["docker", "stop", container_id], check=True)
        subprocess.run(["docker", "rm", container_id], check=True)

        remove_from_database(container_id)

        await interaction.followup.send(embed=discord.Embed(description=f"Instance '{container_name}' removed successfully.", color=0x00ff00))
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(embed=discord.Embed(description=f"Error removing instance: {e}", color=0xff0000))


@bot.tree.command(name="help", description="Shows the help message")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="help", color=0x00ff00)
    embed.add_field(name="/deploy", value="Creates a new Instance with Ubuntu 22.04.", inline=False)
    embed.add_field(name="/remove <ssh_command/Name>", value="Removes a server", inline=False)
    embed.add_field(name="/start <ssh_command/Name>", value="Start a server.", inline=False)
    embed.add_field(name="/stop <ssh_command/Name>", value="Stop a server.", inline=False)
    embed.add_field(name="/regen-ssh <ssh_command/Name>", value="Regenerates SSH cred", inline=False)
    embed.add_field(name="/restart <ssh_command/Name>", value="Stop a server.", inline=False)
    embed.add_field(name="/list", value="List all your servers", inline=False)
    embed.add_field(name="/ping", value="Check the bot's latency.", inline=False)
    embed.add_field(name="/node", value="Check The Node Storage Usage.", inline=False)
    embed.add_field(name="/bal", value="Check Your Balance.", inline=False)
    embed.add_field(name="/renew", value="Renew The VPS.", inline=False)
    embed.add_field(name="/earncredit", value="earn the credit.", inline=False)
    await interaction.response.send_message(embed=embed)


# run the bot
bot.run(TOKEN)
