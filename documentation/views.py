

from django.shortcuts import render
from .models import DocumentationSection
from django.http import HttpResponse
from django.template.loader import render_to_string
from docx import Document
from weasyprint import HTML
import io

def documentation_view(request):
    sections = DocumentationSection.objects.all()
    return render(request, 'documentation/documentation.html', {
        'documentation_sections': sections
    })

# def documentation_view(request):
#     sections = DocumentationSection.objects.all()
#     return render(request, 'documentation/documentation.html', {'sections': sections})

def download_pdf(request):
    sections = DocumentationSection.objects.all()
   # Assuming you are passing `documentation_sections` to the template context
    html = render_to_string('documentation/pdf_template.html', {'documentation_sections': sections})
    pdf = HTML(string=html).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="documentation.pdf"'
    return response

def download_word(request):
    sections = DocumentationSection.objects.all()
    doc = Document()
    doc.add_heading('Website Documentation', 0)
    for sec in sections:
        doc.add_heading(sec.title, level=1)
        doc.add_paragraph(sec.content)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = 'attachment; filename="documentation.docx"'
    return response
