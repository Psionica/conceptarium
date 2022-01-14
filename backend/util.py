import json
from operator import mod
from pathlib import Path
from PIL import Image
import io
from sentence_transformers import util
import torch
import secrets
import time
import numpy as np
from numpy.linalg import norm


def find(modality, query, auth_result, text_encoder, text_image_encoder):
    authorized_thoughts = get_authorized_thoughts(auth_result)

    if len(authorized_thoughts) == 0:
        return []

    query_embeddings = encode(
        modality, query, text_encoder, text_image_encoder)
    sims = []

    for e in authorized_thoughts:
        if modality == 'text':
            if e['modality'] == 'text':
                sims += [np.dot(e['embeddings']['text'], query_embeddings['text']) / (
                    norm(e['embeddings']['text']) * norm(query_embeddings['text']))]
            elif e['modality'] == 'image':
                sims += [np.dot(e['embeddings']['text_image'], query_embeddings['text_image']) / (
                    norm(e['embeddings']['text_image']) * norm(query_embeddings['text_image']))]
        elif modality == 'image':
            sims += [np.dot(e['embeddings']['text_image'], query_embeddings['text_image']) / (
                norm(e['embeddings']['text_image']) * norm(query_embeddings['text_image']))]

    for e_idx, e in enumerate(sims):
        authorized_thoughts[e_idx]['relatedness'] = e
        authorized_thoughts[e_idx]['content'] = get_content(
            authorized_thoughts[e_idx], True)
        authorized_thoughts[e_idx].pop('filename', None)

    authorized_thoughts = sorted(
        authorized_thoughts, key=lambda x: x['relatedness'], reverse=True)

    return authorized_thoughts


def save(modality, query, auth_result, text_encoder, text_image_encoder):
    knowledge_base_path = Path('..') / 'knowledge' / 'base'

    if auth_result['custodian'] == False:
        return {
            'message': 'Only the conceptarium\'s custodian can save thoughts in it.'
        }
    else:
        if not (knowledge_base_path / 'metadata.json').exists():
            json.dump([], open(knowledge_base_path / 'metadata.json', 'w'))

        query_embedding = encode(
            modality, query, text_encoder, text_image_encoder)
        thoughts = json.load(open(knowledge_base_path / 'metadata.json'))

        if modality == 'text':
            duplicates = [e for e in thoughts if e['modality'] ==
                          'text' and open(knowledge_base_path / e['filename']).read() == query]

            if len(duplicates) == 0:
                filename = secrets.token_urlsafe(8) + '.md'
                open(knowledge_base_path / filename, 'w').write(query)
        elif modality == 'image':
            duplicates = [e for e in thoughts if e['modality'] ==
                          'image' and open(knowledge_base_path / e['filename'], 'rb').read() == query]

            if len(duplicates) == 0:
                filename = secrets.token_urlsafe(8) + '.jpg'
                query = Image.open(io.BytesIO(query)).convert('RGB')
                query.save(knowledge_base_path / filename, quality=50)

        if len(duplicates) == 0:
            new_thought = {
                'filename': filename,
                'modality': modality,
                'timestamp': time.time(),
                'interest': 1,
                'embeddings': query_embedding
            }

            thoughts += [new_thought]
            json.dump(thoughts, open(
                knowledge_base_path / 'metadata.json', 'w'))

            return new_thought
        else:
            return {
                'message': 'Duplicate thought found.'
            }


def get_authorized_thoughts(auth_result):
    metadata_path = Path('..') / 'knowledge' / 'base' / 'metadata.json'
    thoughts = json.load(open(metadata_path))

    if auth_result['custodian'] == True:
        return thoughts
    else:
        similarity_threshold = 0.3
        authorized_microverse = auth_result['authorized_microverse']

        if authorized_microverse == []:
            return []

        query_embeddings = authorized_microverse[0]['embeddings']
        sims = []
        for e in thoughts:
            if authorized_microverse[0]['modality'] == 'text':
                if e['modality'] == 'text':
                    sims += [np.dot(e['embeddings']['text'], query_embeddings['text']) / (
                        norm(e['embeddings']['text']) * norm(query_embeddings['text']))]
                elif e['modality'] == 'image':
                    sims += [np.dot(e['embeddings']['text_image'], query_embeddings['text_image']) / (
                        norm(e['embeddings']['text_image']) * norm(query_embeddings['text_image']))]
            elif authorized_microverse[0]['modality'] == 'image':
                sims += [np.dot(e['embeddings']['text_image'], query_embeddings['text_image']) / (
                    norm(e['embeddings']['text_image']) * norm(query_embeddings['text_image']))]

        scored_thoughts = zip(thoughts, sims)
        authorized_thoughts = [e[0]
                               for e in scored_thoughts if e[1] > similarity_threshold]

        return authorized_thoughts


def encode(modality, content, text_encoder, text_image_encoder):
    if modality == 'text':
        return {
            'text_model': 'sentence-transformers/multi-qa-mpnet-base-cos-v1',
            'text_image_model': 'clip-ViT-B-32',
            'text': [round(e, 6) for e in text_encoder.encode(content).tolist()],
            'text_image': [round(e, 6) for e in text_image_encoder.encode(content).tolist()]
        }
    elif modality == 'image':
        return {
            'text_image_model': 'clip-ViT-B-32',
            'text_image': [round(e, 6) for e in text_image_encoder.encode(Image.open(io.BytesIO(content))).tolist()]
        }
    else:
        raise Exception('Can\'t encode content of modality "' + modality + '"')


def get_content(thought, json_friendly=False):
    knowledge_base_path = Path('..') / 'knowledge' / 'base'

    if thought['modality'] == 'text':
        content = open(knowledge_base_path / thought['filename']).read()
    elif thought['modality'] == 'image':
        content = open(knowledge_base_path / thought['filename'], 'rb').read()

        if json_friendly:
            content = thought['filename']

    return content
