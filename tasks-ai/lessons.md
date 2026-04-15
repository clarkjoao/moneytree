# Lessons

- Antes de confiar no nome gerado no upload, validar se ele preserva o tipo real do documento; nomes artificiais podem desviar o parser correto.
- Em PDFs bancários com layout em colunas, evitar `extract_text()` como fonte primária quando a precisão do token monetário importa; preferir `extract_words()` com coordenadas XY para não perder separadores e centavos.
- Quando o frontend precisa mostrar progresso operacional, não deixar o contrato do job implícito em `detail`; expor `kind`, `current_step` e contadores estruturados para evitar parsing frágil na UI.
- Quando uma entidade de domínio precisa sobreviver a reprocessamento ou deduplicação, usar identidade determinística derivada do conteúdo antes de apoiar UX ou overlays em IDs aleatórios.
