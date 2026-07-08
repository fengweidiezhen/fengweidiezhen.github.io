"""
Refactored script to download audio files from S3 with caching support.
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3Client:
    """S3 client wrapper with connection management."""
    
    def __init__(self, access_key: str, secret_key: str, region: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to S3."""
        try:
            self.client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            logger.info(f"Connected to S3 in region {self.region}")
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"AWS credentials error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create S3 client: {e}")
            raise
    
    def list_objects(self, bucket_name: str, prefix: str) -> List[Dict]:
        """
        List all objects with the given prefix.
        
        Args:
            bucket_name: S3 bucket name
            prefix: Object key prefix
            
        Returns:
            List of object metadata dictionaries
        """
        all_objects = []
        continuation_token = None
        
        try:
            while True:
                kwargs = {'Bucket': bucket_name, 'Prefix': prefix}
                if continuation_token:
                    kwargs['ContinuationToken'] = continuation_token
                
                response = self.client.list_objects_v2(**kwargs)
                
                if 'Contents' in response:
                    all_objects.extend(response['Contents'])
                    logger.debug(f"Retrieved {len(all_objects)} objects")
                
                if not response.get('IsTruncated'):
                    break
                
                continuation_token = response.get('NextContinuationToken')
            
            logger.info(f"Found {len(all_objects)} objects with prefix {prefix}")
            return all_objects
            
        except ClientError as e:
            logger.error(f"S3 list objects error: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing objects: {e}")
            return []
    
    def download_file(self, bucket_name: str, key: str, local_path: str) -> bool:
        """
        Download a file from S3.
        
        Args:
            bucket_name: S3 bucket name
            key: S3 object key
            local_path: Local file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            os.makedirs(os.path.dirname(local_path) if os.path.dirname(local_path) else '.', exist_ok=True)
            self.client.download_file(bucket_name, key, local_path)
            return True
        except ClientError as e:
            logger.error(f"Download error for {key}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {key}: {e}")
            return False


class AudioCache:
    """Manage audio file cache and metadata."""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata from file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}")
        return {}
    
    def _save_metadata(self):
        """Save cache metadata to file."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def get_file_path(self, user_id: str, filename: str) -> Path:
        """Get local file path for a cached file."""
        user_dir = self.cache_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / filename
    
    def is_cached(self, user_id: str, filename: str) -> bool:
        """Check if a file is already cached."""
        file_path = self.get_file_path(user_id, filename)
        return file_path.exists()
    
    def add_to_cache(self, user_id: str, filename: str, s3_key: str, 
                    last_modified: str, file_size: int):
        """Add file to cache metadata."""
        cache_key = f"{user_id}/{filename}"
        self.metadata[cache_key] = {
            "s3_key": s3_key,
            "last_modified": last_modified,
            "file_size": file_size,
            "cached_at": datetime.now(timezone.utc).isoformat()
        }
        self._save_metadata()
    
    def get_cached_file(self, user_id: str, filename: str) -> Optional[Path]:
        """Get path to cached file if it exists."""
        if self.is_cached(user_id, filename):
            return self.get_file_path(user_id, filename)
        return None


class TimeParser:
    """Utility class for parsing datetime strings."""
    
    @staticmethod
    def parse_datetime(input_str: str, source_tz: timezone = config.SHANGHAI_TZ) -> datetime:
        """
        Parse datetime string and convert to UTC.
        
        Args:
            input_str: Datetime string
            source_tz: Source timezone (default: Shanghai)
            
        Returns:
            UTC datetime object
        """
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y %H:%M',
            '%m/%d/%Y'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(input_str, fmt)
                dt = dt.replace(tzinfo=source_tz)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse datetime: {input_str}. Use format like '2023-10-01 12:00:00'")


class AudioDownloader:
    """Download audio files from S3 with caching."""
    
    def __init__(self, s3_client: S3Client, cache: AudioCache, download_dir: str):
        self.s3_client = s3_client
        self.cache = cache
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def download_files_in_time_range(self, bucket_name: str, user_id: str,
                                     start_time: datetime, end_time: datetime,
                                     overwrite: bool = False) -> Tuple[int, int]:
        """
        Download files in the specified time range.
        
        Args:
            bucket_name: S3 bucket name
            user_id: User ID
            start_time: Start time (UTC)
            end_time: End time (UTC)
            overwrite: Whether to overwrite existing files
            
        Returns:
            Tuple of (downloaded_count, skipped_count)
        """
        # Ensure times are UTC
        if start_time.tzinfo != timezone.utc:
            start_time = start_time.astimezone(timezone.utc)
        if end_time.tzinfo != timezone.utc:
            end_time = end_time.astimezone(timezone.utc)
        
        folder_prefix = f"profile_audios/{user_id}/"
        
        # List all objects
        objects = self.s3_client.list_objects(bucket_name, folder_prefix)
        
        if not objects:
            logger.info(f"No files found with prefix {folder_prefix}")
            return 0, 0
        
        downloaded_count = 0
        skipped_count = 0
        
        for obj in objects:
            file_time = obj['LastModified']
            
            # Check if file is in time range
            if start_time <= file_time <= end_time:
                file_key = obj['Key']
                filename = os.path.basename(file_key)
                
                # Check cache first
                cached_path = self.cache.get_cached_file(user_id, filename)
                if cached_path and not overwrite:
                    logger.debug(f"File already cached: {filename}")
                    skipped_count += 1
                    continue
                
                # Download to cache
                cache_path = self.cache.get_file_path(user_id, filename)
                
                if self.s3_client.download_file(bucket_name, file_key, str(cache_path)):
                    self.cache.add_to_cache(
                        user_id,
                        filename,
                        file_key,
                        file_time.isoformat(),
                        obj.get('Size', 0)
                    )
                    logger.info(f"Downloaded: {filename} ({file_time.strftime('%Y-%m-%d %H:%M:%S UTC')})")
                    downloaded_count += 1
                else:
                    logger.warning(f"Failed to download: {filename}")
        
        logger.info(f"Download complete - Downloaded: {downloaded_count}, Skipped: {skipped_count}")
        return downloaded_count, skipped_count
    
    def get_audio_files(self, user_id: str, start_time: datetime, 
                       end_time: datetime) -> List[Dict]:
        """
        Get list of audio files for a time range (from cache or S3).
        
        Args:
            user_id: User ID
            start_time: Start time (UTC)
            end_time: End time (UTC)
            
        Returns:
            List of file metadata dictionaries
        """
        folder_prefix = f"profile_audios/{user_id}/"
        objects = self.s3_client.list_objects(config.S3_BUCKET_NAME, folder_prefix)
        
        files = []
        for obj in objects:
            file_time = obj['LastModified']
            if start_time <= file_time <= end_time:
                filename = os.path.basename(obj['Key'])
                cached_path = self.cache.get_cached_file(user_id, filename)
                
                files.append({
                    "filename": filename,
                    "timestamp": file_time.isoformat(),
                    "time_ms": int(file_time.timestamp() * 1000),
                    "cached": cached_path is not None,
                    "path": str(cached_path) if cached_path else None,
                    "s3_key": obj['Key']
                })
        
        return sorted(files, key=lambda x: x['time_ms'])


if __name__ == "__main__":
    # Example usage
    time_parser = TimeParser()
    s3_client = S3Client(config.AWS_ACCESS_KEY, config.AWS_SECRET_KEY, config.AWS_REGION)
    cache = AudioCache(config.CACHE_DIR)
    downloader = AudioDownloader(s3_client, cache, config.AUDIO_DOWNLOAD_DIR)
    
    user_id = "nnRWbEXHxyA"
    start_time_str = "2026-01-16 16:49:45"
    end_time_str = "2026-01-16 17:03:46"
    
    try:
        start_time = time_parser.parse_datetime(start_time_str)
        end_time = time_parser.parse_datetime(end_time_str)
        
        logger.info(f"Downloading files from {start_time} to {end_time}")
        downloaded, skipped = downloader.download_files_in_time_range(
            config.S3_BUCKET_NAME,
            user_id,
            start_time,
            end_time,
            overwrite=False
        )
        
        logger.info(f"Download process complete - Downloaded: {downloaded}, Skipped: {skipped}")
    except ValueError as e:
        logger.error(f"Time parsing error: {e}")
    except Exception as e:
        logger.error(f"Download error: {e}")
