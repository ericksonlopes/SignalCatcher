from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = r'D:\signalcatcher-505023-dcafb0efaeab.json'

def authenticate_service_account():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"ERRO: O arquivo '{SERVICE_ACCOUNT_FILE}' não foi encontrado.")
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Erro ao autenticar: {e}")
        return None

def list_items(service, folder_id=None):
    """Lista arquivos e pastas. Se folder_id for passado, lista o que tem DENTRO dela."""
    
    if folder_id:
        print(f"\nVisualizando conteúdo DENTRO da pasta (ID: {folder_id})...")
    else:
        print("\nVisualizando TUDO que foi compartilhado com o robô...")
        
    try:
        query = "trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
            
        results = service.files().list(
            q=query,
            pageSize=50, 
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])

        if not items:
            print('Nenhum item encontrado nesta visualização.')
        else:
            pastas = [item for item in items if item['mimeType'] == 'application/vnd.google-apps.folder']
            arquivos = [item for item in items if item['mimeType'] != 'application/vnd.google-apps.folder']
            
            print(f"\n--- [PASTAS ENCONTRADAS] ({len(pastas)}) ---")
            for p in pastas:
                print(f"[PASTA] {p['name']} (ID: {p['id']})")
                
            print(f"\n--- [ARQUIVOS ENCONTRADOS] ({len(arquivos)}) ---")
            for a in arquivos:
                print(f"[ARQUIVO] {a['name']} (ID: {a['id']})")
                
    except Exception as e:
        print(f"Erro ao tentar listar: {e}")

if __name__ == '__main__':
    service = authenticate_service_account()
    if service:
        # 1. Primeiro, listamos tudo que você compartilhou com a conta de serviço
        list_items(service)
        
        # 2. Se quiser ver o que tem DENTRO de uma pasta específica, descomente abaixo
        # e coloque o ID da pasta (que vai aparecer na listagem acima)
        # list_items(service, folder_id='COLOQUE_O_ID_DA_PASTA_AQUI')
