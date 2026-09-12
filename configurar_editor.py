"""Cria ou substitui as credenciais locais sem gravar a senha em texto puro."""
import getpass
import hashlib
import json
import secrets
from pathlib import Path


def configure(username, password):
    salt = secrets.token_bytes(32)
    data = {'username': username, 'salt': salt.hex(), 'password_hash': hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000).hex()}
    (Path(__file__).parent/'.editor-secrets.json').write_text(json.dumps(data), encoding='utf-8')


if __name__ == '__main__':
    username = input('Usuário: ').strip()
    password = getpass.getpass('Senha: ')
    if not username or len(password) < 8:
        raise SystemExit('Informe o usuário e uma senha com pelo menos 8 caracteres.')
    if password != getpass.getpass('Confirme a senha: '):
        raise SystemExit('As senhas não coincidem.')
    configure(username, password)
    print('Credenciais locais configuradas.')
