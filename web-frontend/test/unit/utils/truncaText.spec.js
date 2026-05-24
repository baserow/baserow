import { truncateText } from '../../../modules/core/utils/string.js'
//const truncateText = require('../../../modules/core/utils/string.js')
//import { Vitest, describe, test, expect } from 'vitest/node';
import { describe, test, expect, toBe } from 'vitest'

describe("Truncate Text Caixa Preta", () => {
    test("Tamanho do texto igual ao limite", () =>{
        expect(truncateText('abcd', 4)).toBe('abcd');
    });
    test("Tamanho do texto menor que o limite", ()=>{
        expect(truncateText('abcd', 5)).toBe('abcd');
    });
    test("Tamanho do texto maior que o limite", ()=>{
        expect(truncateText('abcd', 3)).toBe('abc...')
    })

    test("Limite negativo", ()=>{
        expect(truncateText('abcd', -1)).toBe('');
    })
    test("Limite zero", ()=>{
        expect(truncateText('abcd', 0)).toBe('');
    })
    test("Entrada invalida", ()=>{
        expect(truncateText(123, 5)).toBe('');
    });
});