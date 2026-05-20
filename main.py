from fastapi import FastAPI, Request, Form, UploadFile, File, Query
  from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
  from fastapi.staticfiles import StaticFiles
  from fastapi.templating import Jinja2Templates
  from openai import OpenAI
  import json
  import re
  from typing import List, Optional
  from config import settings
  from prompts import (
      CUSTOMER_PROFILE_PROMPT,
      FOLLOWUP_PLAN_PROMPT,
      OBJECTION_HANDLING_PROMPT,
      SILENT_REACTIVATION_PROMPT,
      FULL_ANALYSIS_PROMPT
  )
  from document_processor import doc_processor
  from database import db

  app = FastAPI(title="销售成单推演 Agent")

  try:
      app.mount("/static", StaticFiles(directory="static"), name="static")
  except:
      pass
  templates = Jinja2Templates(directory="templates")

  client = OpenAI(
      api_key=settings.kimi_api_key,
      base_url=settings.kimi_base_url
  )

  def call_kimi(prompt: str) -> dict:
      try:
          response = client.chat.completions.create(
              model=settings.kimi_text_model,
              max_tokens=settings.max_tokens,
              temperature=settings.temperature,
              messages=[{"role": "user", "content": prompt}]
          )
          content = response.choices[0].message.content
          try:
              json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
              if json_match:
                  return json.loads(json_match.group(1))
              return json.loads(content)
          except:
              return {"raw_response": content}
      except Exception as e:
          return {"error": str(e)}

  @app.get("/", response_class=HTMLResponse)
  async def index(request: Request):
      return templates.TemplateResponse("index.html", {"request": request})

  @app.get("/customers", response_class=HTMLResponse)
  async def customers_page(request: Request):
      return templates.TemplateResponse("customers.html", {"request": request})

  @app.get("/customers/{customer_id}", response_class=HTMLResponse)
  async def customer_detail_page(request: Request, customer_id: int):
      customer = db.get_customer(customer_id)
      if not customer:
          return RedirectResponse(url="/customers")
      return templates.TemplateResponse("customer_detail.html", {
          "request": request,
          "customer": customer
      })

  @app.post("/api/customers")
  async def create_customer(
      name: str = Form(...),
      company: str = Form(None),
      industry: str = Form(None),
      phone: str = Form(None),
      email: str = Form(None),
      notes: str = Form(None)
  ):
      try:
          customer_id = db.create_customer(
              name=name, company=company, industry=industry,
              phone=phone, email=email, notes=notes
          )
          return JSONResponse({
              "success": True,
              "customer_id": customer_id,
              "message": "客户创建成功"
          })
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.get("/api/customers")
  async def get_customers(search: str = Query(None), industry: str = Query(None)):
      try:
          customers = db.get_customers(search=search, industry=industry)
          return JSONResponse({"success": True, "customers": customers})
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.get("/api/customers/{customer_id}")
  async def get_customer(customer_id: int):
      try:
          customer = db.get_customer(customer_id)
          if not customer:
              return JSONResponse({"success": False, "error": "客户不存在"}, status_code=404)
          latest_profile = db.get_latest_profile(customer_id)
          analysis_histories = db.get_analysis_histories(customer_id)
          chat_histories = db.get_chat_histories(customer_id)
          return JSONResponse({
              "success": True,
              "customer": customer,
              "latest_profile": latest_profile,
              "analysis_count": len(analysis_histories),
              "chat_count": len(chat_histories)
          })
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.delete("/api/customers/{customer_id}")
  async def delete_customer(customer_id: int):
      try:
          success = db.delete_customer(customer_id)
          if success:
              return JSONResponse({"success": True, "message": "客户删除成功"})
          else:
              return JSONResponse({"success": False, "error": "客户不存在"}, status_code=404)
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.post("/api/customers/{customer_id}/chat")
  async def add_chat_history(
      customer_id: int,
      content: str = Form(...),
      source_type: str = Form("manual"),
      files: List[UploadFile] = File(None)
  ):
      try:
          customer = db.get_customer(customer_id)
          if not customer:
              return JSONResponse({"success": False, "error": "客户不存在"}, status_code=404)
          all_content = []
          processed_files = []
          if files:
              for file in files:
                  file_content = await file.read()
                  result = doc_processor.process_file(file_content, file.filename)
                  if result['type'] != 'unsupported':
                      all_content.append(f"=== {file.filename} ===\n{result['content']}")
                      processed_files.append({
                          "filename": file.filename,
                          "type": result['type'],
                          "content": result['content']
                      })
          if content.strip():
              all_content.append(content.strip())
          if not all_content:
              return JSONResponse({"success": False, "error": "没有提供聊天记录内容"}, status_code=400)
          final_content = "\n\n".join(all_content)
          chat_id = db.add_chat_history(
              customer_id=customer_id,
              content=final_content,
              source_type=source_type if not files else "file_upload",
              source_file=", ".join([f['filename'] for f in processed_files]) if processed_files else None
          )
          return JSONResponse({
              "success": True,
              "chat_id": chat_id,
              "message": "聊天记录添加成功",
              "processed_files": processed_files
          })
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.get("/api/statistics")
  async def get_statistics():
      try:
          stats = db.get_statistics()
          return JSONResponse({"success": True, "statistics": stats})
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.post("/api/customers/{customer_id}/analyze")
  async def analyze_customer_with_history(
      customer_id: int,
      analysis_type: str = Form("full"),
      new_chat: str = Form(None),
      include_history: bool = Form(True)
  ):
      try:
          customer = db.get_customer(customer_id)
          if not customer:
              return JSONResponse({"success": False, "error": "客户不存在"}, status_code=404)
          history_chat = ""
          if include_history:
              history_chat = db.get_all_chat_content(customer_id)
          final_chat = history_chat
          if new_chat and new_chat.strip():
              if final_chat:
                  final_chat += "\n\n=== 最新记录 ===\n" + new_chat.strip()
              else:
                  final_chat = new_chat.strip()
          customer_info = customer.get('notes', '') or ''
          if not final_chat and not customer_info:
              return JSONResponse({
                  "success": False,
                  "error": "没有足够的客户信息进行分析，请先添加聊天记录或客户备注"
              }, status_code=400)
          previous_profile = db.get_latest_profile(customer_id)
          if analysis_type == "profile":
              prompt = CUSTOMER_PROFILE_PROMPT.format(
                  industry=customer.get('industry', '未知'),
                  customer_info=customer_info,
                  chat_history=final_chat or "暂无详细聊天记录"
              )
          elif analysis_type == "full":
              if previous_profile:
                  profile_context = f"\n\n之前对该客户的画像分析：\n{json.dumps(previous_profile.get('profile_data', {}), ensure_ascii=False)}"
                  prompt = FULL_ANALYSIS_PROMPT.format(
                      industry=customer.get('industry', '未知'),
                      customer_info=customer_info + profile_context,
                      chat_history=final_chat or "暂无详细聊天记录"
                  )
              else:
                  prompt = FULL_ANALYSIS_PROMPT.format(
                      industry=customer.get('industry', '未知'),
                      customer_info=customer_info,
                      chat_history=final_chat or "暂无详细聊天记录"
                  )
          else:
              return JSONResponse({"success": False, "error": "未知的分析类型"}, status_code=400)
          result = call_kimi(prompt)
          db.save_analysis(
              customer_id=customer_id,
              analysis_type=analysis_type,
              result=result,
              chat_summary=final_chat[:500] if final_chat else None
          )
          if analysis_type == "profile" and "性格类型" in result:
              db.save_profile(customer_id, result)
          return JSONResponse({
              "success": True,
              "result": result,
              "message": "分析完成并已保存"
          })
      except Exception as e:
          return JSONResponse({"success": False, "error": str(e)}, status_code=500)

  @app.get("/api/health")
  async def health():
      return {"status": "ok", "model": settings.kimi_text_model}
