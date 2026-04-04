from __future__ import annotations

from backend.models.transaction import Transaction


def is_fatura_payment_line(descricao: str) -> bool:
    upper = descricao.upper()
    if "ITAU BLACK" in upper:
        return True
    if "FATURA PAGA PERSON MULTI" in upper:
        return True
    if "PAGAMENTO" in upper and "FATURA" in upper:
        return True
    return False


def flatten_for_analysis(transaction: Transaction, mes_origem: str) -> dict:
    parcela = transaction.parcela_info
    classification = transaction.classificacao
    categoria = classification.categoria
    excluir_gasto = transaction.tipo == "debito" and (
        categoria in ("Transferência Interna", "Receita")
        or is_fatura_payment_line(transaction.descricao_original)
    )
    excluir_receita = transaction.tipo == "credito" and categoria == "Transferência Interna"
    return {
        "id": transaction.id,
        "mes_origem": mes_origem,
        "data": transaction.data.isoformat(),
        "valor": float(transaction.valor),
        "tipo": transaction.tipo,
        "meio": transaction.meio,
        "descricao_original": transaction.descricao_original,
        "fonte": transaction.fonte,
        "categoria": categoria,
        "natureza": classification.natureza,
        "recorrencia": classification.recorrencia,
        "compromisso": classification.compromisso,
        "contexto": classification.contexto,
        "metodo": classification.metodo,
        "parcela_numero": parcela.numero if parcela else None,
        "parcela_total": parcela.total if parcela else None,
        "excluir_gasto": excluir_gasto,
        "excluir_receita": excluir_receita,
    }
