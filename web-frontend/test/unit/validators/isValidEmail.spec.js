import { isValidEmail } from '../../../modules/core/validators'

describe('isValidEmail - Testes de Caixa-Preta e Caixa-Branca', () => {

  // ==========================================
  // CAIXA-PRETA: Particionamento de Equivalência (EP)
  // ==========================================
  describe('Caixa-Preta: Particionamento de Equivalência (EP)', () => {
    test('EP-01: e-mail válido retorna true', () => {
      expect(isValidEmail('usuario@dominio.com')).toBe(true)
    })

    test('EP-02: e-mail com subdomínio retorna true', () => {
      expect(isValidEmail('a@sub.dominio.org')).toBe(true)
    })

    test('EP-03: sem arroba retorna false', () => {
      expect(isValidEmail('usuariodominio.com')).toBe(false)
    })

    test('EP-04: sem extensão de domínio retorna false', () => {
      expect(isValidEmail('usuario@dominio')).toBe(false)
    })

    test('EP-05: string vazia retorna false', () => {
      expect(isValidEmail('')).toBe(false)
    })

    test('EP-06: null retorna false', () => {
      expect(isValidEmail(null)).toBe(false)
    })

    test('EP-07: espaços internos retorna false', () => {
      expect(isValidEmail('usu ario@dominio.com')).toBe(false)
    })
    
    test('EP-08: dois arrobas retorna false', () => {
      expect(isValidEmail('a@@dominio.com')).toBe(false)
    })
  })

  // ==========================================
  // CAIXA-PRETA: Análise de Valor Limite (BVA)
  // ==========================================
  describe('Caixa-Preta: Análise de Valor Limite (BVA)', () => {
    test('BVA-01: mínimo válido possível (a@b.c) retorna true', () => {
      expect(isValidEmail('a@b.c')).toBe(true)
    })

    test('BVA-02: mínimo inválido (@.) retorna false', () => {
      expect(isValidEmail('@.')).toBe(false)
    })

    test('BVA-03: ponto no final do domínio (a@b.) retorna false', () => {
      expect(isValidEmail('a@b.')).toBe(false)
    })
  })
  // ==========================================
  // CAIXA-BRANCA: Branch Coverage e MC/DC
  // ==========================================
  describe('Caixa-Branca: Cobertura de Branches e MC/DC', () => {
    
    // Condição 1 (C1): !email
    // Condição 2 (C2): typeof email !== 'string'

    test('MC/DC [M1]: email válido (C1=false, C2=false) -> Branch falso (avança pro regex)', () => {
      // Como não é vazio e é string, passa pelo IF e o regex decide.
      expect(isValidEmail('teste@teste.com')).toBe(true)
    })

    test('MC/DC [M2]: email falsy como undefined (C1=true) -> Branch verdadeiro (retorna false)', () => {
      // Testa a independência da primeira condição
      expect(isValidEmail(undefined)).toBe(false)
    })

    test('MC/DC [M3]: tipo não é string, ex: número (C1=false, C2=true) -> Branch verdadeiro (retorna false)', () => {
      // Testa a independência da segunda condição. Existe um valor (C1=false), mas o tipo é errado (C2=true).
      // Os testes de Caixa-Preta do PDF não incluíam explicitamente testar a passagem de um número ou objeto!
      expect(isValidEmail(12345)).toBe(false)
      expect(isValidEmail(['array@teste.com'])).toBe(false)
    })
  })
})