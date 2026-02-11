---
description: Analyze the optimized Codebase and find points of optimization
---

# Optimize Codebase for AI Agents

## Objective
Identify optimization opportunities in the codebase to enhance AI agent performance, reduce token costs, and improve maintainability.

## Process
### 1. Analyze Current Codebase
- Review current architecture and data flow of the codebase, analyze the core workflows, note which files and tools are used. Also note their frequency of use and their approximate token cost.
- Identify bottlenecks and inefficiencies in the current implementation, such as redundant code, unnecessary API calls, or inefficient data handling.

### 2. Identify Optimization Opportunities
- Look for areas where code can be refactored to reduce complexity and improve readability.
- Think about ways to minimize token usage, such as caching results, reducing the number of API calls, or optimizing data structures.
- Ask yourself the question: "What can I take out of the codebase that would reduce token costs and improve performance without sacrificing functionality?" **Note:** This is a critical question to ask, as it encourages you to think about what is truly necessary for the AI agents to function effectively.
- Consider the trade-offs between optimization and maintainability. Ensure that any optimizations do not make the codebase more difficult to understand or maintain.

## Output
### 1. Document Findings
- Create a quickly readable informationdense report listing the identified optimization opportunities, their potential impact on performance and token costs, and any trade-offs involved. (Use bullet points for clarity and conciseness.)
- Give the optimization opportunities a rating from 1-10 based on their potential impact and ease of implementation.

### 2. User Feedback
- Ask the User to review the report and provide feedback on which optimizations they would like to prioritize for implementation.

### 3. Optimization optimization
- Based on the User's feedback, prioritize the identified optimizations and identify the integration points for implementing these optimizations in the codebase, aswell as checking the real world implementability of the optimizations.
- Ouput you findings in the format mentioned above