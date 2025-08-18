import PyPDF2
import sys

def add_header(header_pdf_path, original_pdf_path, output_pdf_path):

    with open(header_pdf_path, 'rb') as header_file, \
         open(original_pdf_path, 'rb') as original_file:

        header_pdf_reader = PyPDF2.PdfReader(header_file)
        original_pdf_reader = PyPDF2.PdfReader(original_file)

        pdf_writer = PyPDF2.PdfWriter()

        header_page = header_pdf_reader.pages[0]

        for page_num in range(len(original_pdf_reader.pages)):

            empty_page = PyPDF2.PageObject.create_blank_page(
                None, header_pdf_reader.pages[0].mediabox.width,
                header_pdf_reader.pages[0].mediabox.height
            )
            empty_page.merge_page(header_page)
            empty_page.merge_page(original_pdf_reader.pages[page_num])

            pdf_writer.add_page(empty_page)

        with open(output_pdf_path, 'wb') as output_file:
            pdf_writer.write(output_file)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 <script_name>.py header.pdf document.pdf output.pdf")
        sys.exit(1)

    header_path = sys.argv[1]
    document_path = sys.argv[2]
    output_path = sys.argv[3]

    add_header(header_path, document_path, output_path)
