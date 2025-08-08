import ast
import datetime
import pickle
import re
import time
from datetime import timedelta

import discord
import os
from difflib import SequenceMatcher
from pathlib import Path
import logging
import traceback
import requests
import urllib3
from discord import CallMessage, GroupCall

from dotenv import load_dotenv
from discord_fast_api_bridge import FastAPIMediaBridge as media_bridge

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
urllib3.disable_warnings()

class MediaSelfBot(discord.Client):
    def __init__(self, media_folder=os.getenv('MEDIA_PATH')):

        super().__init__()

        self.sounds_folder = Path(media_folder) / "Musique"
        self.video_folder = Path(media_folder) / "Video"
        self.supported_formats = {'.ogg', '.mp3','.wav', ".mp4", ".av1"}

        self.sound_cache = {}  # {filename_stem: file_path}
        self.video_cache = {}  # {filename_stem: file_path}

        # Check if sounds folder exists
        if not self.sounds_folder.exists():
            logger.error(f"Sounds folder does not exist: {self.sounds_folder}")
            raise FileNotFoundError(f"Sounds folder not found: {self.sounds_folder}")

        if not self.video_folder.exists():
            logger.error(f"Sounds folder does not exist: {self.sounds_folder}")
            raise FileNotFoundError(f"Sounds folder not found: {self.sounds_folder}")

    async def on_ready(self):
        channel = await self.fetch_channel(1116010901586321448)
        msg0 = await channel.send("# Bozobot is connected to discord 🌍")
        logger.info(f'{self.user} selfbot is ready!')
        logger.info(f'Sounds folder: {self.sounds_folder.absolute()}')
        logger.info('Loading sound cache (this may take a moment)...')
        await msg0.delete()
        msg1 = await channel.send("# Bozobot is loading sound cache... 🔃")
        await self.load_sound_cache()
        await self.load_video_cache()

        await msg1.delete()
        await channel.send("# Bozobot is fully ready ✅")
        logger.info('✅ Sound cache loaded and ready!')

    async def load_sound_cache(self, force=False):
        """Load all sound file names into cache for fast searching"""

        try:
            if os.path.exists('sound_cache.pkl') and not force:
                with open('sound_cache.pkl', 'rb') as f:
                    self.sound_cache, sound_files, folders_scanned = pickle.load(f)

                print(f'✅ Loaded cache from file: {len(sound_files)} sound files')
                return

            sound_files = []
            folders_scanned = set()
            self.sound_cache = {}

            for root, dirs, files in os.walk(self.sounds_folder, followlinks=True):
                for file in files:
                    file_path = Path(root) / file

                    if 'Elvis' in str(file_path.absolute()):
                        continue

                    if file_path.suffix.lower() in self.supported_formats:
                        print(f"✅ Adding: {file_path.stem}")
                        self.sound_cache[file_path.stem] = file_path
                        sound_files.append(file_path.stem)
                        folders_scanned.add(str(file_path.parent.relative_to(self.sounds_folder)))

            logger.info(f'Cached {len(sound_files)} sound files across {len(folders_scanned)} folders')
            logger.info(f'Sample folders: {", ".join(sorted(folders_scanned)[:5])}{"..." if len(folders_scanned) > 5 else ""}')
            if sound_files:
                logger.info(f'Sample sounds: {", ".join(sorted(sound_files)[:10])}{"..." if len(sound_files) > 10 else ""}')

            with open('sound_cache.pkl', 'wb') as f:
                print(f'✅ Saving cache to file: {f.name}...')
                pickle.dump((self.sound_cache, sound_files, folders_scanned), f)

        except Exception as e:
            logger.error(f"Error loading sound cache: {e}")

    async def load_video_cache(self, force=False):
        """Load all video file names into cache for fast searching"""

        try:
            if os.path.exists('video_cache.pkl') and not force:
                with open('video_cache.pkl', 'rb') as f:
                    self.video_cache, video_files, folders_scanned = pickle.load(f)

                print(f'✅ Loaded cache from file: {len(video_files)} video files')
                return

            video_files = []
            folders_scanned = set()
            self.video_cache = {}

            for file_path in self.video_folder.rglob('*'):
                if 'Elvis' in str(file_path.absolute()):
                    continue
                if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                    print(file_path)
                    # Store both the stem (filename without extension) and full path
                    self.video_cache[file_path.stem] = file_path
                    video_files.append(file_path.stem)
                    folders_scanned.add(str(file_path.parent.relative_to(self.video_folder)))

            logger.info(f'Cached {len(video_files)} videos files across {len(folders_scanned)} folders')
            logger.info(f'Sample folders: {", ".join(sorted(folders_scanned)[:5])}{"..." if len(folders_scanned) > 5 else ""}')
            if video_files:
                logger.info(f'Sample videos: {", ".join(sorted(video_files)[:10])}{"..." if len(video_files) > 10 else ""}')

            with open('video_cache.pkl', 'wb') as f:
                print(f'✅ Saving cache to file: {f.name}...')
                pickle.dump((self.video_cache, video_files, folders_scanned), f)

        except Exception as e:
            logger.error(f"Error loading sound cache: {e}")

    async def on_message(self, message: discord.Message):
        start = time.time_ns()
        # Check for !search command

        if f'<@{self.user.id}>' in message.content or (message.reference and message.reference.resolved.author.id == self.user.id): # TODO: Link using a discord MCP
            try:
                pass

            except Exception as e:
                logger.error(f"Error with BozoAI: {e}")
                try:
                    await message.reply(f"❌ BozoAI encountered an error: {str(e)}")
                except:
                    pass
        elif message.content.startswith('!vc'):
            call = message.channel.call

            if not isinstance(call, discord.calls.GroupCall):
                await message.reply("No voice call right now...")
                return

            await call.fetch_message()
            callMessage = call.message

            delta = timedelta(seconds=int(time.time()) - int(callMessage.created_at.timestamp()))

            await message.reply(f"# ⏳ Voice duration {delta}\n\n{" | ".join([member.mention for member in call.members if member.id != self.user.id])}")
        elif message.content.startswith('!ring'):
            await message.channel.call.ring()
            await message.reply("*calling everyone...*")
        elif message.content.startswith('!start'):
            query = message.content[6:].strip()  # Remove '!start ' prefix
            if not query.isdigit():
                await message.reply(f"❌ You need to add the server id")
                return

            servers = requests.post(f"https://{os.getenv('IP')}:8443/api/v2/servers/{query}/action/start_server", headers={"Authorization": f"Bearer {os.getenv('CRAFTY')}"}, verify=False).json()

            if servers['status'] == 'ok':
                await message.reply(f"✅ The server {query} has been started")
            else:
                await message.reply(f"❌ Crafty error: {servers}")

        elif message.content.startswith('!search '):
            query = message.content[8:].strip()  # Remove '!search ' prefix
            if query:
                matches = await self.search_sounds(query)

                if not matches:
                    if len(self.sound_cache) > 0:
                        await message.reply(content="❌ No sound founds.")
                    else:
                        await message.reply(content="❌ Sound cache not loaded yet.")
                    return

                result_text = f"🔍 **Search Results for '{query}'**\n\n"

                for file_path, ratio in matches:
                    if not os.path.exists(file_path):
                        matches.remove((file_path, ratio))

                    match_indicator = "🎯" if ratio > 0.9 else "🔍" if ratio > 0.7 else "❓"
                    result_text += f"{match_indicator} **{file_path.stem}** - Match: {ratio:.0%}\n"

                result_text+= f"-# *Searched through {len(self.sound_cache)} files _in {int(time.time_ns() - start) / 1000000000}s_*"

                await message.reply(content=result_text)
            else:
                await message.reply(content="❌ Please specify a search query: `!search query`")

        elif message.content.startswith('!vsearch '):
            query = message.content[9:].strip()  # Remove '!vsearch ' prefix
            if query:
                matches = await self.search_videos(query)

                if not matches:
                    if len(self.video_cache) > 0:
                        await message.reply(content="❌ No video founds.")
                    else:
                        await message.reply(content="❌ Video cache not loaded yet.")
                    return

                result_text = f"🔍 **Search Results for '{query}'**\n\n"

                for file_path, ratio in matches:
                    if not os.path.exists(file_path):
                        matches.remove((file_path, ratio))

                    match_indicator = "🎯" if ratio > 0.9 else "🔍" if ratio > 0.7 else "❓"
                    result_text += f"{match_indicator} **{file_path.stem}** - Match: {ratio:.0%}\n"

                result_text+= f"-# *Searched through {len(self.video_cache)} files _in {int(time.time_ns() - start) / 1000000000}s_*"

                await message.reply(content=result_text)
            else:
                await message.reply(content="❌ Please specify a search query: `!search query`")

        elif message.content.startswith('!crafty'):
            msg = await message.reply(content="🙏 Please wait...")

            try:
                servers = requests.get(f"https://{os.getenv('IP')}:8443/api/v2/servers", headers={"Authorization": f"Bearer {os.getenv('CRAFTY')}"}, verify=False)
                if servers.status_code != 200 or servers.json()["status"] != "ok":
                    logger.error(servers.text)
                    await msg.edit(content=f"❌ Crafty responded with an error. `{servers.json()['status']}`")
                else:
                    server_data = servers.json()["data"]

                    if not server_data:
                        await msg.edit(content="📭 No servers found!")
                        return

                    embed_content = "🖥️ **Crafty Servers Overview**\n\n"

                    for i, server in enumerate(server_data, 1):
                        stats = requests.get(f"https://{os.getenv('IP')}:8443/api/v2/servers/{server['server_id']}/stats", headers={"Authorization": f"Bearer {os.getenv('CRAFTY')}"}, verify=False).json()['data']

                        embed_content += f"**{i}. {server['server_name']} {"🟢" if stats['running'] else "🔴"}**"
                        embed_content += f"🌐 Address: `mc.appolon.dev{f':{server['server_port']}' if server['server_port'] != 25565 else ''}`\n"
                        embed_content += f"☕ Type: `{'Java' if 'java' in server.get('type') else 'Bedrock'}{' ' + stats['version'] if stats['version'] != 'False' else ''}`\n"

                        if stats['running']:
                            embed_content += f"🎛️ Ram: `{stats['mem']}` Cpu: `{stats['cpu']}`\n"

                        embed_content += f"💾 Disk: `{stats['world_size']}`\n"

                        players: list[str] = ast.literal_eval(stats['players']) if ast.literal_eval(stats['players']) else []
                        embed_content += f"🎮 Players:{f' {len(players)}' if len(players) != 0 else ''} {'None' if len(players) == 0 else ', '.join(players)}\n"

                        embed_content += f"-# UUID: {stats['server_id']['server_id']}\n"

                        if i < len(server_data):
                            embed_content += "─────────────────────\n"

                    embed_content += f"\n📊 **Total Servers:** {len(server_data)}"

                    await msg.edit(content=embed_content)

            except Exception as e:
                logger.error(f"Error crafty: {e}")
                await msg.edit(content=f"❌ An error occured while talking with crafty. `{e}`")

        elif message.content.startswith('!shuffle '):
            await message.reply(content="🔀 Shuffle started")


        elif message.content.startswith('!skip '):
            await message.reply(content="⏩ Skiped a song")

        elif message.content.startswith('!play '):
            sound_name = message.content[6:].strip()
            if sound_name.lower() == '$random':
                import random
                random_sound_name = random.choice(list(self.sound_cache.keys()))
                await self.web_play_sound(message, random_sound_name)
            elif sound_name:
                await self.web_play_sound(message, sound_name)
            else:
                await message.reply(content="❌ Please specify a sound name: `!play sound_name`")

        elif message.content.startswith('!url '):
            url = message.content[4:].strip()
            if url:
                await self.web_play_url(message, url)
            else:
                await message.reply(content="❌ Please specify a sound name: `!url uri`")

        elif message.content.startswith('!loop '):
            sound_name = message.content[6:].strip()
            if sound_name.lower() == '$random':
                import random
                random_sound_name = random.choice(list(self.sound_cache.keys()))
                await self.web_play_sound(message, random_sound_name), True
            elif sound_name:
                await self.web_play_sound(message, sound_name, True)
            else:
                await message.reply(content="❌ Please specify a sound name: `!play sound_name`")

        elif message.content.startswith('!vplay '):
            video_name = message.content[7:].strip()
            if video_name:
                await self.web_play_video(message, video_name)
            else:
                await message.reply(content="❌ Please specify a sound name: `!vplay video_name`")
        elif message.content.startswith('!stop'):
            await self.web_stop(message)
        elif message.content.startswith('!pause'):
            await self.web_pause(message)

        # Check for !webstatus command
        elif message.content == '!status':
            await self.web_status(message)

        # Check for !reload command (reload cache)
        elif message.content == '!reload':
            await self.reload_cache(message)

        elif message.content.startswith('!'):
            await message.reply("❌ Command not found")

    async def search_sounds(self, query: str):
        """
        Search for the best matching sounds in self.sound_cache

        Args:
            query: Search query string

        Returns:
            List of tuples: [(filepath, score), ...] for easy unpacking
        """
        if not self.sound_cache:
            return []

        def normalize_string(s: str) -> str:
            """Normalize string for comparison by removing extra whitespace and converting to lowercase"""
            return ' '.join(s.lower().strip().split())

        def extract_base_name(name: str) -> str:
            """Extract base name without parentheses content and everything after dash"""
            # Remove everything in parentheses
            base = re.sub(r'\s*\([^)]*\)\s*', '', name)
            # Remove everything after dash (including the dash)
            base = re.sub(r'\s*-\s*.*$', '', base)
            return normalize_string(base)

        def calculate_similarity(stem: str, query: str) -> float:
            """Calculate similarity score between stem and query"""
            normalized_stem = normalize_string(stem)
            normalized_query = normalize_string(query)

            # Extract base names (without parentheses and dashes)
            base_stem = extract_base_name(stem)
            base_query = extract_base_name(query)

            # Calculate different similarity scores
            full_similarity = SequenceMatcher(None, normalized_stem, normalized_query).ratio()
            base_similarity = SequenceMatcher(None, base_stem, base_query).ratio()

            # Check for exact matches
            if normalized_stem == normalized_query:
                return 1.0
            elif base_stem == base_query and base_stem:  # Exact base match (excluding empty strings)
                # High score for base match with small penalty for extra content
                has_stem_extra = '(' in stem or '-' in stem
                has_query_extra = '(' in query or '-' in query
                if has_stem_extra and not has_query_extra:
                    return 0.92  # Query is cleaner version of stem
                elif has_query_extra and not has_stem_extra:
                    return 0.92  # Stem is cleaner version of query
                else:
                    return 0.95  # Both have or don't have extra content

            # For partial matches, prioritize base name similarity but consider full name too
            # Weight base similarity more heavily
            combined_score = (base_similarity * 0.7) + (full_similarity * 0.3)

            # Boost score if query is contained in stem (but not vice versa for exact containment)
            if normalized_query in normalized_stem and normalized_query != normalized_stem:
                combined_score = min(0.95, combined_score + 0.15)  # Cap at 95% for containment

            # Boost score if base query is contained in base stem (but not vice versa)
            if base_query in base_stem and base_query != base_stem:
                combined_score = min(0.90, combined_score + 0.1)  # Cap at 90% for base containment

            return combined_score

        # Calculate scores for all items
        scored_results = []
        for stem, filepath in self.sound_cache.items():
            score = calculate_similarity(stem, query)
            scored_results.append((stem, filepath, score))

        # Sort by score (descending) and return top results
        scored_results.sort(key=lambda x: x[2], reverse=True)

        # Return only filepath and ratio for easy unpacking
        return [(filepath, score) for stem, filepath, score in scored_results[:5]]

    async def search_videos(self, query: str):
        """
        Search for the best matching videos in self.video_cache

        Args:
            query: Search query string

        Returns:
            List of tuples: [(filepath, score), ...] for easy unpacking
        """
        if not self.video_cache:
            return []

        def normalize_string(s: str) -> str:
            """Normalize string for comparison by removing extra whitespace and converting to lowercase"""
            return ' '.join(s.lower().strip().split())

        def extract_base_name(name: str) -> str:
            """Extract base name without parentheses content and everything after dash"""
            # Remove everything in parentheses
            base = re.sub(r'\s*\([^)]*\)\s*', '', name)
            # Remove everything after dash (including the dash)
            base = re.sub(r'\s*-\s*.*$', '', base)
            return normalize_string(base)

        def calculate_similarity(stem: str, query: str) -> float:
            """Calculate similarity score between stem and query"""
            normalized_stem = normalize_string(stem)
            normalized_query = normalize_string(query)

            # Extract base names (without parentheses and dashes)
            base_stem = extract_base_name(stem)
            base_query = extract_base_name(query)

            # Calculate different similarity scores
            full_similarity = SequenceMatcher(None, normalized_stem, normalized_query).ratio()
            base_similarity = SequenceMatcher(None, base_stem, base_query).ratio()

            # Check for exact matches
            if normalized_stem == normalized_query:
                return 1.0
            elif base_stem == base_query and base_stem:  # Exact base match (excluding empty strings)
                # High score for base match with small penalty for extra content
                has_stem_extra = '(' in stem or '-' in stem
                has_query_extra = '(' in query or '-' in query
                if has_stem_extra and not has_query_extra:
                    return 0.92  # Query is cleaner version of stem
                elif has_query_extra and not has_stem_extra:
                    return 0.92  # Stem is cleaner version of query
                else:
                    return 0.95  # Both have or don't have extra content

            # For partial matches, prioritize base name similarity but consider full name too
            # Weight base similarity more heavily
            combined_score = (base_similarity * 0.7) + (full_similarity * 0.3)

            # Boost score if query is contained in stem (but not vice versa for exact containment)
            if normalized_query in normalized_stem and normalized_query != normalized_stem:
                combined_score = min(0.95, combined_score + 0.15)  # Cap at 95% for containment

            # Boost score if base query is contained in base stem (but not vice versa)
            if base_query in base_stem and base_query != base_stem:
                combined_score = min(0.90, combined_score + 0.1)  # Cap at 90% for base containment

            return combined_score

        # Calculate scores for all items
        scored_results = []
        for stem, filepath in self.video_cache.items():
            score = calculate_similarity(stem, query)
            scored_results.append((stem, filepath, score))

        # Sort by score (descending) and return top results
        scored_results.sort(key=lambda x: x[2], reverse=True)

        # Return only filepath and ratio for easy unpacking
        return [(filepath, score) for stem, filepath, score in scored_results[:5]]

    async def reload_cache(self, message):
        """Reload the video cache"""
        old_sound_cache = self.sound_cache
        old_video_cache = self.video_cache


        await message.reply(content="🔄 Reloading media cache from NAS...")

        try:
            start_sound = time.time()
            await self.load_sound_cache(True)
            end_sound = time.time()

            start_video = time.time()
            await self.load_video_cache(True)
            end_video = time.time()

            await message.reply(content=f"✅ Cache reloaded! Found {len(self.sound_cache) - len(old_sound_cache)} new sound files. (took {int(end_sound - start_sound)}s)")
            await message.reply(content=f"✅ Cache reloaded! Found {len(self.video_cache) - len(old_video_cache)} new video files. (took {int(end_video - start_video)}s)")
        except Exception as e:
            logger.error(f"Error reloading cache: {e}")
            await message.reply(content=f"❌ Error reloading cache: {str(e)}")

    async def web_play_sound(self, message, query, loop=False):
        """Play a sound on the web interface using FastAPI bridge"""
        try:

            if self.sound_cache == 0:
                await message.reply(content="❌ Sound cache not loaded yet.")

            # Check if FastAPI server is running
            if not media_bridge.get_server_status():
                await message.reply(content="❌ Web server is not running. Start the FastAPI server first.")
                return

            # Find the best matching sound file
            matches = await self.search_sounds(query)

            if not matches:
                await message.reply(content=f"❌ No sound found matching '{query}'")
                return

            sound_path, match_ratio = matches[0]

            if match_ratio < 0.8:
                await message.reply(content=f"❌ No sound matched enough '{query}' (maybe you meant '{sound_path.stem}'?)")
                return

            success = media_bridge.trigger_audio_playback(sound_path, loop=loop)

            if success:
                active_clients = media_bridge.get_active_connections()
                if query.lower() == '$stop':
                    await message.reply(content=
                                        f"# Stoped music\n"
                                        f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                        )
                else:
                    await message.reply(content=
                                       f"# __{sound_path.stem}__ is now playing in VC\n"
                                       f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                       )
            else:
                await message.reply(content="❌ Failed to trigger web playback. No client connected.")

        except ImportError:
            await message.reply(content="❌ FastAPI bridge not available. Make sure discord_fastapi_bridge.py is in the same folder.")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Web play error: {e}")
            await message.reply(content=f"❌ Error with web playback: {str(e)}")

    async def web_play_video(self, message, query):
        """Play a video on the web interface using FastAPI bridge"""
        try:

            if self.video_cache == 0:
                await message.reply(content="❌ Video cache not loaded yet.")

            # Check if FastAPI server is running
            if not media_bridge.get_server_status():
                print(media_bridge.get_server_status())
                await message.reply(content="❌ Web server is not running. Start the FastAPI server first.")
                return

            # Find the best matching video file
            matches = await self.search_videos(query)

            if not matches:
                await message.reply(content=f"❌ No video found matching '{query}'")
                return

            video_path, match_ratio = matches[0]

            if match_ratio < 0.8:
                await message.reply(content=f"❌ No video matched enough '{query}' (maybe you meant '{video_path.stem}'?)")
                return

            success = media_bridge.trigger_video_playback(video_path)

            if success:
                active_clients = media_bridge.get_active_connections()
                if query.lower() == '$stop':
                    await message.reply(content=
                                        f"# Stoped music\n"
                                        f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                        )
                else:
                    await message.reply(content=
                                       f"# __{video_path.stem}__ is now playing in VC\n"
                                       f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                       )
            else:
                await message.reply(content="❌ Failed to trigger web playback. No client connected.")

        except ImportError:
            await message.reply(content="❌ FastAPI bridge not available. Make sure discord_fastapi_bridge.py is in the same folder.")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Web play error: {e}")
            await message.reply(content=f"❌ Error with web playback: {str(e)}")

    async def web_status(self, message):
        """Check web audio server status"""
        try:
            if media_bridge.get_server_status():
                active_clients = media_bridge.get_active_connections()
                await message.reply(content=
                                   f"# ✅ Web server is running\n"
                                   f"- {len(self.sound_cache)} Cached sounds\n"
                                   f"- {len(self.video_cache)} Cached videos\n"
                                   f"- {active_clients} Connected clients\n"
                                   f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                   )
            else:
                await message.reply(content="❌ Web server is not running")

        except ImportError:
            await message.reply(content="❌ FastAPI bridge not available")
        except Exception as e:
            await message.reply(content=f"❌ Error checking web status: {str(e)}")

    async def web_stop(self, message):
        try:
            if media_bridge.get_server_status():
                active_clients = media_bridge.get_active_connections()
                media_bridge.stop_media()
                await message.reply(content=
                                    f"# ✅ Media stoped\n"
                                    f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                    )
            else:
                await message.reply(content="❌ Web server is not running")

        except ImportError:
            await message.reply(content="❌ FastAPI bridge not available")
        except Exception as e:
            await message.reply(content=f"❌ Error checking web status: {str(e)}")

    async def web_pause(self, message):
        try:
            if media_bridge.get_server_status():
                active_clients = media_bridge.get_active_connections()
                media_bridge.pause_media()
                status, media_status = media_bridge.get_server_status()
                await message.reply(content=
                                    f"# ✅ Media {media_status}\n" 
                                    f"-# 📺 Bozobot connected: {'✅' if active_clients >= 1 else '❌'}"
                                    )
            else:
                await message.reply(content="❌ Web server is not running")

        except ImportError:
            await message.reply(content="❌ FastAPI bridge not available")
        except Exception as e:
            await message.reply(content=f"❌ Error checking web status: {str(e)}")

    async def web_play_url(self, message, url):
        pass


# Configuration
USER_TOKEN = os.getenv('TOKEN')  # Load token from .env file

def main():
    """Main function to run the selfbot"""

    # Check for user token
    if not USER_TOKEN:
        print("❌ User token not found in .env file")
        print("Please create a .env file with TOKEN=your_user_token_here")
        return

    # Create and run selfbot
    try:
        selfbot = MediaSelfBot()
        selfbot.run(USER_TOKEN)
        media_bridge.bot = selfbot

    except FileNotFoundError as e:
        print(f"❌ {e}")
    except discord.LoginFailure:
        print("❌ Invalid user token. Please check your TOKEN in the .env file.")
    except Exception as e:
        print(f"❌ Error running selfbot: {e}")


if __name__ == "__main__":
    main()