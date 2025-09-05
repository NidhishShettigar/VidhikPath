# from django.shortcuts import render, redirect
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.conf import settings
# from openai import OpenAI


# client = OpenAI(api_key=settings.OPENAI_API_KEY)


# def chat_api(request):
#         gpt_prompt = (
#             f"User Question: {message}\n\n"
#             f"Relevant IPC Context:\n{rag_context}\n\n"
#             f"Answer in detail with reference to the context."
#         )

#         # 6. Call GPT-4o chat API
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": "You are an expert legal assistant providing answers based on the Indian Penal Code."},
#                 {"role": "user", "content": gpt_prompt}
#             ],
#             max_tokens=1000,
#             temperature=0.2
#         )



# def summarize_chunk(chunk):
#     prompt = f"Summarize the legal text below:\n\n{chunk}"
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "You are a legal document summarizer."},
#             {"role": "user", "content": prompt}
#         ],
#         max_tokens=500,
#         temperature=0.2
#     )
#     return response.choices[0].message.content
