"""Storage-Abstraktion: lokales Dateisystem (Dev) oder S3/Garage (Produktion).

Beide Backends adressieren Objekte ueber POSIX-artige Keys wie
"scenes/<id>/pano.jpg". Oeffentliche URLs beginnen in beiden Faellen mit
/media/ — lokal bedient die App diesen Pfad selbst, in Produktion proxied
Caddy ihn auf den Garage-Web-Endpoint.
"""
import mimetypes
import os
import shutil
from pathlib import Path


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        p = self.root / key
        if ".." in Path(key).parts:
            raise ValueError(f"Ungueltiger Key: {key}")
        return p

    def put_bytes(self, key, data):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def put_file(self, src, key):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, p)

    def get_bytes(self, key):
        p = self._path(key)
        return p.read_bytes() if p.is_file() else None

    def exists(self, key):
        return self._path(key).is_file()

    def list(self, prefix=""):
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                key = p.relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    yield key

    def delete_prefix(self, prefix):
        if not prefix:
            raise ValueError("delete_prefix ohne Prefix verweigert")
        for key in list(self.list(prefix)):
            self._path(key).unlink()

    def url(self, key):
        return "/media/" + key


class S3Storage:
    def __init__(self, bucket):
        import boto3

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=os.environ["S3_ENDPOINT"],
            region_name=os.environ.get("S3_REGION", "garage"),
            aws_access_key_id=os.environ["S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        )

    @staticmethod
    def _ctype(key):
        return mimetypes.guess_type(key)[0] or "application/octet-stream"

    def put_bytes(self, key, data):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                               ContentType=self._ctype(key))

    def put_file(self, src, key):
        self.client.upload_file(str(src), self.bucket, key,
                                ExtraArgs={"ContentType": self._ctype(key)})

    def get_bytes(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.ClientError:
            return None

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def list(self, prefix=""):
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]

    def delete_prefix(self, prefix):
        if not prefix:
            raise ValueError("delete_prefix ohne Prefix verweigert")
        batch = []
        for key in self.list(prefix):
            batch.append({"Key": key})
            if len(batch) == 1000:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})
                batch = []
        if batch:
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})

    def url(self, key):
        return "/media/" + key


def make_stores(data_dir):
    """(media, originals) je nach STORAGE-Umgebungsvariable."""
    if os.environ.get("STORAGE", "local") == "s3":
        return (S3Storage(os.environ.get("S3_BUCKET_MEDIA", "media")),
                S3Storage(os.environ.get("S3_BUCKET_ORIGINALS", "originals")))
    data_dir = Path(data_dir)
    return LocalStorage(data_dir / "media"), LocalStorage(data_dir / "originals")
