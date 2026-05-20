import io
  import base64
  from openai import OpenAI
  from config import settings

  class DocumentProcessor:
      def __init__(self):
          self.client = OpenAI(
              api_key=settings.kimi_api_key,
              base_url=settings.kimi_base_url
          )
          self.supported_image = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
          self.supported_doc = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md']

      def process_file(self, file_content: bytes, filename: str) -> dict:
          ext = filename.lower().split('.')[-1] if '.' in filename else ''
          full_ext = '.' + ext

          if full_ext in self.supported_image:
              return self._process_image(file_content, filename)
          elif full_ext in ['.txt', '.md']:
              return {'type': 'text', 'content': file_content.decode('utf-8', errors='ignore'), 'filename': filename}
          elif full_ext == '.pdf':
              return self._process_pdf(file_content, filename)
          elif full_ext in ['.docx', '.doc']:
              return self._process_word(file_content, filename)
          elif full_ext in ['.xlsx', '.xls']:
              return self._process_excel(file_content, filename)
          else:
              return {'type': 'unsupported', 'content': f'不支持的文件格式: {full_ext}', 'filename': filename}

      def _process_image(self, file_content: bytes, filename: str) -> dict:
          try:
              base64_image = base64.b64encode(file_content).decode('utf-8')
              response = self.client.chat.completions.create(
                  model=settings.kimi_vision_model,
                  messages=[{
                      "role": "user",
                      "content": [
                          {"type": "text", "text": "请提取图片中的所有文字内容，保持原有格式。如果是聊天记录截图，请提取对话内容。"},
                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                      ]
                  }]
              )
              return {'type': 'image', 'content': response.choices[0].message.content, 'filename': filename}
          except Exception as e:
              return {'type': 'error', 'content': f'图片处理失败: {str(e)}', 'filename': filename}

      def _process_pdf(self, file_content: bytes, filename: str) -> dict:
          try:
              import PyPDF2
              pdf_file = io.BytesIO(file_content)
              reader = PyPDF2.PdfReader(pdf_file)
              text = ""
              for page in reader.pages:
                  text += page.extract_text() + "\n"
              return {'type': 'pdf', 'content': text, 'filename': filename}
          except Exception as e:
              return {'type': 'error', 'content': f'PDF处理失败: {str(e)}', 'filename': filename}

      def _process_word(self, file_content: bytes, filename: str) -> dict:
          try:
              import docx
              doc_file = io.BytesIO(file_content)
              doc = docx.Document(doc_file)
              text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
              return {'type': 'word', 'content': text, 'filename': filename}
          except Exception as e:
              return {'type': 'error', 'content': f'Word处理失败: {str(e)}', 'filename': filename}

      def _process_excel(self, file_content: bytes, filename: str) -> dict:
          try:
              import pandas as pd
              excel_file = io.BytesIO(file_content)
              df = pd.read_excel(excel_file)
              return {'type': 'excel', 'content': df.to_string(), 'filename': filename}
          except Exception as e:
              return {'type': 'error', 'content': f'Excel处理失败: {str(e)}', 'filename': filename}

  doc_processor = DocumentProcessor()
