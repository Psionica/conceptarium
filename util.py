from sentence_transformers import SentenceTransformer, util
from PIL import Image
import io
import pickle
import os
import time
import numpy as np
import pprint

metadata_path = 'conceptarium/metadata.pickle'


def init():
    if not os.path.exists(metadata_path):
        pickle.dump(list(), open(metadata_path, 'wb'))


def save(thought):
    conceptarium = pickle.load(open(metadata_path, 'rb'))

    modality_match = [e.modality == thought.modality for e in conceptarium]
    corpus_embeddings = [e.embedding for e in conceptarium]

    results = util.semantic_search(
        [thought.embedding], corpus_embeddings, top_k=len(corpus_embeddings), score_function=util.dot_score)[0]
    results = [e if modality_match[e['corpus_id']]
               else compensate_modality_mismatch(e) for e in results]

    for result in results:
        conceptarium[result['corpus_id']
                     ].interest += min(result['score'], 1) ** 4

    conceptarium += [thought]
    pickle.dump(conceptarium, open(metadata_path, 'wb'))


def find(query, model, relatedness, activation, noise, silent, top_k):
    conceptarium = pickle.load(open(metadata_path, 'rb'))

    query_embedding = embed(query, model)
    query_modality = get_modality(query)

    modality_match = [e.modality == query_modality for e in conceptarium]
    corpus_embeddings = [e.embedding for e in conceptarium]

    results = util.semantic_search(
        [query_embedding], corpus_embeddings, top_k=len(corpus_embeddings), score_function=util.dot_score)[0]
    results = [e if modality_match[e['corpus_id']]
               else compensate_modality_mismatch(e) for e in results]

    if not silent:
        for result in results:
            conceptarium[result['corpus_id']
                         ].interest += min(result['score'], 1) ** 4
        pickle.dump(conceptarium, open(metadata_path, 'wb'))

    for idx, result in enumerate(results):
        results[idx]['score'] = (relatedness * result['score']
                                 + activation *
                                 (np.log(conceptarium[result['corpus_id']].interest / (1 - 0.9)) - 0.9 * np.log((time.time() - conceptarium[result['corpus_id']].timestamp) / (3600 * 24) + 0.1))) \
            * np.random.normal(1, noise)

    results = sorted(
        results, key=lambda result: result['score'], reverse=True)
    memories = [conceptarium[e['corpus_id']] for e in results][:top_k]
    return memories


def get_doc_paths(directory):
    paths = []

    for root, directories, files in os.walk(directory):
        for filename in files:
            path = os.path.join(root, filename)
            paths.append(path)

    return paths


def load_model():
    return SentenceTransformer('clip-ViT-B-32')


def embed(content, model):
    if get_modality(content) == 'language':
        return model.encode(content, convert_to_tensor=True, normalize_embeddings=True)
    else:
        return model.encode(Image.open(io.BytesIO(content)), convert_to_tensor=True, normalize_embeddings=True)


def reset_embeddings(model):
    conceptarium = pickle.load(open(metadata_path, 'rb'))
    for thought_idx, thought in enumerate(conceptarium):
        if thought.modality == 'language':
            content = open(thought.filename, 'r').read()
        else:
            content = open(thought.filename, 'rb').read()
        conceptarium[thought_idx].embedding = embed(content, model)

    pickle.dump(conceptarium, open(metadata_path, 'wb'))


def get_modality(content):
    if isinstance(content, str):
        return 'language'
    else:
        return 'imagery'


def compensate_modality_mismatch(result):
    result['score'] *= 2.5
    return result


class Thought:
    def __init__(self, filename, content, model):
        self.filename = filename
        self.modality = get_modality(content)
        self.timestamp = time.time()
        self.interest = 1
        self.embedding = embed(content, model)
