
1. Context: 

Explain the context of the project.
1. regulation, import export, tarif code

2. Scope and Constraints 

Scope : 

Limited corpus food, china tarif, 
Data ingestion from regulation docs pipeline,

Use case driven development.3/4 cases done.


3. Tests/Demo : 
4. Improvements


What to do : 

Create chapter graph for nc2024. Need to give pages from chapter beginning.  
LLm should get the graph for better context.

pdf -> Graph. 
RAG contains graph data as context. 
LLm retreival improved.

Can this work for other 

korea agreement : 
1. search with code 
2. Understand tariff exemption. use graph 

doubt: separate treatment for each agreement?

medical products : only select category, no inf in price.
ce : not applicable for tariff calc.

select perimeter/scope.

perimeter : 

1. Cost calculations : 
cost calculation based on nc code, agreement between eu-country. nc code, maroc, coree du sud. If agreement 
not in corpus for ex india china then do not calc and 
report error. 

2. Legal documents : 
We do not consider CE Regulations, Origin protocol, 
Conformity or notified organism.

Code de douane de union european is for legal matters
out of scope for this. But needs to be checked.
Check if medical documents impact price.

3. Parts of Relevant documents : 
Medical : category of medical item. 
CE : category of ce? need to be rechecked. 

4. Tech scope : 
Use cheap models for fast iteration. 
Create context tree for product context pdf

What is left to be done : 

1. Tree creation for pdf 
2. Testing testcases with tree input in system prompt
3. Finalizing cost calculation create real cost manually tested
4. Automatic validation tests for the 7 products
5. Presentation 5pages
6. Documentation 

