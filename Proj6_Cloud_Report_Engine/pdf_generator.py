from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

def generate_pdf(lead_info: dict, result_data: dict):
    """Generates a high-fidelity PDF using Jinja2 templates and WeasyPrint."""
    
    # 1. Point Jinja2 to the 'templates' folder
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('report.html')
    
    # 2. Inject the dynamic Python variables into the HTML template
    html_content = template.render(
        business_name=lead_info["business_name"],
        score=result_data["final_score"],
        tier=result_data["tier"],
        leaks=result_data["growth_leaks"]
    )
    
    # 3. Generate the PDF
    filename = f"{lead_info['business_name'].replace(' ', '_')}_Report.pdf"
    HTML(string=html_content).write_pdf(filename)
    print(f"📄 PDF successfully generated: {filename}")