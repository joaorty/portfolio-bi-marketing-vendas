// ====================================================================
// SCRIPT POWER QUERY - CARREGAR TODOS OS DADOS DO DASHBOARD
// ====================================================================
// Copie e cole este código no Power Query do Power BI
// Ou use: Página Inicial > Nova Fonte > Consulta em Branco
// ====================================================================

let
    // ================== CONFIGURAÇÃO DO CAMINHO ==================
    // ALTERE ESTE CAMINHO PARA A PASTA ONDE ESTÃO SEUS CSVs
    CaminhoPasta = "",
    
    // ================== FUNÇÃO AUXILIAR ==================
    CarregarCSV = (nomeArquivo as text) =>
        let
            Fonte = Csv.Document(
                File.Contents(CaminhoPasta & nomeArquivo),
                [Delimiter=",", Columns=null, Encoding=65001, QuoteStyle=QuoteStyle.None]
            ),
            PromoverCabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true])
        in
            PromoverCabecalhos,
    
    // ================== TABELAS FATO ==================
    
    FATO_PERFORMANCE_DIARIA = 
        let
            Fonte = CarregarCSV("FATO_PERFORMANCE_DIARIA.csv"),
            TiposDefinidos = Table.TransformColumnTypes(Fonte,{
                {"Data", type date},
                {"Canal", type text},
                {"Campanha", type text},
                {"Investimento", type number},
                {"Impressoes", Int64.Type},
                {"Cliques", Int64.Type},
                {"Conversoes", Int64.Type},
                {"Pedidos", type number},
                {"Receita", type number},
                {"Novos_Clientes", type number}
            }, "en-US")
        in
            TiposDefinidos,
    
    FATO_VENDAS = 
        let
            Fonte = CarregarCSV("FATO_VENDAS.csv"),
            TiposDefinidos = Table.TransformColumnTypes(Fonte,{
                {"ID_Pedido", type text},
                {"Data", type date},
                {"ID_Cliente", type text},
                {"Cliente_Novo", Int64.Type},
                {"Segmento_Cliente", type text},
                {"Regiao_Cliente", type text},
                {"Produto", type text},
                {"Receita", type number},
                {"Canal_Aquisicao", type text},
                {"Campanha_Aquisicao", type text},
                {"Canal", type text},
                {"Campanha", type text},
                {"Data_Aquisicao", type date},
                {"Status_Cliente", type text},
                {"Dias_Desde_Aquisicao", Int64.Type},
                {"Tipo_Venda", type text}
            }, "en-US"),
            // Converter Cliente_Novo de 0/1 para logical
            ConverterLogical = Table.TransformColumns(TiposDefinidos, {{"Cliente_Novo", each _ = 1, type logical}})
        in
            ConverterLogical,
    
    // ================== TABELAS DIMENSÃO ==================
    
    DIM_CLIENTES = 
        let
            Fonte = CarregarCSV("DIM_CLIENTES.csv"),
            TiposDefinidos = Table.TransformColumnTypes(Fonte,{
                {"ID_Cliente", type text},
                {"Data_Aquisicao", type date},
                {"Canal_Aquisicao", type text},
                {"Campanha_Aquisicao", type text},
                {"Segmento", type text},
                {"Regiao", type text},
                {"Total_Pedidos", Int64.Type},
                {"LTV", type number},
                {"Status", type text},
                {"Cohort", type text}
            }, "en-US")
        in
            TiposDefinidos,
    
    DIM_CALENDAR = 
        let
            DataInicial = #date(2022, 1, 1),
            DataFinal   = #date(2024, 12, 31),

            ListaDatas = List.Dates(
                DataInicial,
                Duration.Days(DataFinal - DataInicial) + 1,
                #duration(1,0,0,0)
            ),

            Tabela = Table.FromList(
                ListaDatas,
                Splitter.SplitByNothing(),
                {"Data"}
            ),

            AddAno = Table.AddColumn(Tabela, "Ano", each Date.Year([Data]), Int64.Type),
            AddMes = Table.AddColumn(AddAno, "Mes_Numero", each Date.Month([Data]), Int64.Type),
            AddMesNome = Table.AddColumn(AddMes, "Mes_Nome", each Date.MonthName([Data], "pt-BR"), type text),
            AddTrimestre = Table.AddColumn(AddMesNome, "Trimestre", each Date.QuarterOfYear([Data]), Int64.Type),
            AddSemana = Table.AddColumn(AddTrimestre, "Semana", each Date.WeekOfYear([Data]), Int64.Type),
            AddDiaSemana = Table.AddColumn(AddSemana, "Dia_Semana", each Date.DayOfWeekName([Data], "pt-BR"), type text),
            AddDiaMes = Table.AddColumn(AddDiaSemana, "Dia_Mes", each Date.Day([Data]), Int64.Type),
            AddFimSemana = Table.AddColumn(AddDiaMes, "Fim_Semana", each Date.DayOfWeek([Data], Day.Monday) >= 5, type logical),

            AddAnoMes = Table.AddColumn(AddFimSemana, "Ano_Mes", each Date.ToText([Data], "yyyy-MM"), type text),

            AddBlackFriday = Table.AddColumn(
                AddAnoMes,
                "Black_Friday",
                each Date.Month([Data]) = 11 and Date.Day([Data]) >= 20 and Date.Day([Data]) <= 30,
                type logical
            ),

            AddNatal = Table.AddColumn(
                AddBlackFriday,
                "Natal",
                each Date.Month([Data]) = 12,
                type logical
            )
        in
            AddNatal,
    
    DIM_METAS = 
        let
            Fonte = CarregarCSV("DIM_METAS.csv"),
            TiposDefinidos = Table.TransformColumnTypes(Fonte,{
                {"Data", type date},
                {"Meta_Receita", type number},
                {"Meta_Pedidos", Int64.Type},
                {"Meta_Novos_Clientes", Int64.Type},
                {"Meta_ROAS", type number}
            }, "en-US")
        in
            TiposDefinidos,
    
    // ================== RESULTADO ==================
    // Retorna todas as tabelas como um registro
    TodasTabelas = [
        FATO_PERFORMANCE_DIARIA = FATO_PERFORMANCE_DIARIA,
        FATO_VENDAS = FATO_VENDAS,
        DIM_CLIENTES = DIM_CLIENTES,
        DIM_CALENDAR = DIM_CALENDAR,
        DIM_METAS = DIM_METAS
    ]
in
    TodasTabelas

