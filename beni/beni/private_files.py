from django.http import FileResponse, Http404


def private_image_response(file_field):
    if not file_field or not file_field.name:
        raise Http404
    try:
        file_object = file_field.open('rb')
    except FileNotFoundError as exc:
        raise Http404 from exc

    header = file_object.read(12)
    file_object.seek(0)
    if header.startswith(b'\xff\xd8\xff'):
        content_type = 'image/jpeg'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        content_type = 'image/png'
    elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        content_type = 'image/webp'
    else:
        file_object.close()
        raise Http404
    response = FileResponse(
        file_object,
        as_attachment=False,
        filename=file_field.name.rsplit('/', 1)[-1],
        content_type=content_type,
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def private_document_response(file_field):
    if not file_field or not file_field.name:
        raise Http404
    try:
        file_object = file_field.open('rb')
    except FileNotFoundError as exc:
        raise Http404 from exc
    header = file_object.read(1024)
    file_object.seek(0)
    if b'%PDF-' in header:
        content_type = 'application/pdf'
    elif header.startswith(b'\xff\xd8\xff'):
        content_type = 'image/jpeg'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        content_type = 'image/png'
    elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        content_type = 'image/webp'
    else:
        file_object.close()
        raise Http404
    response = FileResponse(
        file_object,
        as_attachment=True,
        filename=file_field.name.rsplit('/', 1)[-1],
        content_type=content_type,
    )
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
