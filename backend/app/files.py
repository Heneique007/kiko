"""Bounded, UID-owned, RAM-only attachments. Nothing is executed or persisted."""
import asyncio
import base64
import io
import logging
import re
import secrets
import time
import warnings
import zipfile
from pathlib import Path
from fastapi import HTTPException
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from pypdf import PdfReader, apply_configuration
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from .config import limits

# Suppress parser diagnostics that could quote document bytes.
logging.getLogger('pypdf').addHandler(logging.NullHandler())
logging.getLogger('pypdf').propagate = False
register_heif_opener()
Image.MAX_IMAGE_PIXELS = 16_000_000
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif', '.pdf', '.docx', '.txt', '.md', '.csv', '.json', '.xlsx', '.pptx'}
IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif'}
TEXT = {'.txt', '.md', '.csv', '.json'}


def clean_filename(name):
    name = (name or 'ficheiro').replace('\\', '/').split('/')[-1]
    return re.sub(r'[\x00-\x1f\x7f]', '', name).strip().strip('.')[:140] or 'ficheiro'


def validate_office(data, ext):
    """Allow OOXML only; bound decompression and reject DTD/external XML entities."""
    expected = {'.docx': 'word/document.xml', '.xlsx': 'xl/workbook.xml', '.pptx': 'ppt/presentation.xml'}[ext]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > 1500 or sum(i.file_size for i in infos) > 25 * 1024 * 1024:
            raise ValueError('Oversized OOXML')
        if expected not in archive.namelist():
            raise ValueError('Wrong OOXML format')
        for item in infos:
            if item.flag_bits & 1 or item.file_size > 12 * 1024 * 1024 or item.file_size > max(1, item.compress_size) * 250:
                raise ValueError('Unsafe OOXML')
            if item.filename.endswith(('.xml', '.rels')):
                xml = archive.read(item).lower()
                if b'<!doctype' in xml or b'<!entity' in xml:
                    raise ValueError('Unsafe XML')


def prepare_file(data, ext):
    cap = limits()['max_doc_chars']
    page_limited = False
    if ext in IMAGES:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                accepted = {'.jpg': {'JPEG'}, '.jpeg': {'JPEG'}, '.png': {'PNG'}, '.gif': {'GIF'}, '.webp': {'WEBP'}, '.heic': {'HEIF'}, '.heif': {'HEIF'}}
                if source.format not in accepted[ext]:
                    raise ValueError('Wrong image format')
                source.seek(0)  # Animated images: first frame only.
                image = ImageOps.exif_transpose(source)
                image.thumbnail((2048, 2048))
                if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    flattened = Image.new('RGB', image.size, 'white')
                    flattened.paste(rgba, mask=rgba.getchannel('A'))
                    image = flattened
                else:
                    image = image.convert('RGB')
                buf = io.BytesIO()
                image.save(buf, format='JPEG', quality=88)
                return 'image', buf.getvalue(), False
    if ext in TEXT:
        text = data.decode('utf-8-sig', errors='strict')
        if '\x00' in text:
            raise ValueError('Binary text')
        if ext == '.json':
            import json
            json.loads(text)
    else:
        if ext != '.pdf':
            validate_office(data, ext)
        parts = []
        length = 0
        def add(value):
            nonlocal length
            if length <= cap:
                part = str(value)[:cap + 1 - length]
                parts.append(part)
                length += len(part) + 1
        if ext == '.pdf':
            if not data.startswith(b'%PDF-'):
                raise ValueError('Not a PDF')
            with apply_configuration(
                maximum_declared_stream_length=8 * 1024 * 1024,
                array_based_stream_maximum_output_length=8 * 1024 * 1024,
                lzw_maximum_output_length=8 * 1024 * 1024,
                run_length_maximum_output_length=8 * 1024 * 1024,
                zlib_maximum_output_length=8 * 1024 * 1024,
                image_maximum_buffer_size=8 * 1024 * 1024,
                stream_decoding_work_maximum_length=32 * 1024 * 1024,
                page_tree_maximum_entries=10000,
            ):
                reader = PdfReader(io.BytesIO(data), strict=False)
                if reader.is_encrypted:
                    raise ValueError('Encrypted PDF')
                decompressed = 0
                for page in reader.pages[:100]:
                    contents = page.get_contents()
                    decompressed += len(contents.get_data()) if contents is not None else 0
                    if decompressed > 25 * 1024 * 1024:
                        raise ValueError('Oversized PDF content')
                    add(page.extract_text() or '')
                    if length > cap:
                        break
                if len(reader.pages) > 100:
                    page_limited = True
                    add('[Apenas as primeiras 100 páginas foram extraídas.]')
        elif ext == '.docx':
            doc = Document(io.BytesIO(data))
            for paragraph in doc.paragraphs:
                add(paragraph.text)
            for table in doc.tables:
                for row in table.rows:
                    add(' | '.join(c.text for c in row.cells))
        elif ext == '.xlsx':
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
            try:
                for sheet in book.worksheets[:20]:
                    add(f'Folha: {sheet.title}')
                    for row in sheet.iter_rows(max_row=10000, max_col=100, values_only=True):
                        add(' | '.join('' if v is None else str(v) for v in row))
                        if length > cap:
                            break
                    if length > cap:
                        break
            finally:
                book.close()
        elif ext == '.pptx':
            presentation = Presentation(io.BytesIO(data))
            for i, slide in enumerate(presentation.slides):
                add(f'Diapositivo {i + 1}')
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        add(shape.text)
                    if shape.has_table:
                        for row in shape.table.rows:
                            add(' | '.join(c.text for c in row.cells))
                if length > cap:
                    break
        text = '\n'.join(parts)
    if not text.strip():
        raise ValueError('No extractable text')
    truncated = len(text) > cap or page_limited
    return 'text', text[:cap], truncated


class FileStore:
    def __init__(self):
        self.items = {}
        self.lock = asyncio.Lock()
        self.processing = asyncio.Semaphore(1)

    def _prune(self):
        now = time.time()
        for fid, item in list(self.items.items()):
            if item['expires_at'] <= now:
                del self.items[fid]

    async def prune(self):
        async with self.lock:
            self._prune()

    def public(self, item):
        return {k: item[k] for k in ('id', 'filename', 'bytes', 'expires_at', 'kind', 'truncated')}

    async def save(self, uid, filename, data):
        settings = limits()
        name = clean_filename(filename)
        ext = Path(name).suffix.lower()
        if ext not in EXTENSIONS:
            raise HTTPException(415, 'Formato não suportado. Arquivos ZIP não são aceites.')
        if not data:
            raise HTTPException(422, 'O ficheiro está vazio.')
        cap = settings['max_file_bytes']
        if ext in IMAGES:
            cap = min(cap, settings['max_image_bytes'])
        elif ext in {'.csv', '.xlsx'}:
            cap = min(cap, settings['max_spreadsheet_bytes'])
        if len(data) > cap:
            raise HTTPException(413, 'O ficheiro excede o tamanho permitido.')
        try:
            async with self.processing:
                kind, content, truncated = await asyncio.to_thread(prepare_file, data, ext)
        except Exception:
            raise HTTPException(422, 'Ficheiro inválido, protegido ou sem texto extraível. PDFs digitalizados precisam de OCR; XLSX precisa de valores calculados guardados.') from None
        cost = max(len(data), len(content.encode('utf-8') if isinstance(content, str) else content))
        async with self.lock:
            self._prune()
            if len(self.items) >= settings['max_files'] or sum(i['cost'] for i in self.items.values()) + cost > settings['max_total_bytes']:
                raise HTTPException(413, 'Armazenamento temporário cheio. Remova anexos ou aguarde a expiração.')
            fid = 'file-' + secrets.token_urlsafe(24)
            item = {'id': fid, 'uid': uid, 'filename': name, 'bytes': len(data), 'cost': cost, 'kind': kind,
                    'content': content, 'truncated': truncated, 'expires_at': time.time() + settings['file_ttl_hours'] * 3600}
            self.items[fid] = item
            return self.public(item)

    async def get(self, uid, fid):
        async with self.lock:
            self._prune()
            item = self.items.get(fid)
            if not item or item['uid'] != uid:
                raise HTTPException(404, 'Anexo inexistente ou expirado. Volte a anexar o ficheiro.')
            return dict(item)

    async def delete(self, uid, fid):
        async with self.lock:
            self._prune()
            item = self.items.get(fid)
            if not item or item['uid'] != uid:
                raise HTTPException(404, 'Anexo inexistente ou expirado.')
            del self.items[fid]

    async def part(self, uid, fid):
        item = await self.get(uid, fid)
        if item['kind'] == 'image':
            encoded = base64.b64encode(item['content']).decode('ascii')
            return {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + encoded}}
        suffix = '\n[Texto truncado ao limite configurado.]' if item['truncated'] else ''
        return {'type': 'text', 'text': f'[Documento fornecido pelo utilizador: {item["filename"]}]\n{item["content"]}{suffix}\n[Fim do documento]'}


store = FileStore()
