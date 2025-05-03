app.registerExtension({
    name: "comfy.ollama.widgets",
    
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "ComfyUI_LLM_Ollama") {
            // 重写节点模板
            const originalOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                originalOnExecuted?.apply(this, arguments);
                
                // 添加可调整大小的文本域
                setTimeout(() => {
                    // 为prompt和system_message添加特性
                    this.querySelectorAll(
                        'textarea[data-input-name="prompt"],' + 
                        'textarea[data-input-name="system_message"]'
                    ).forEach(textarea => {
                        // 添加可调整样式
                        textarea.style.resize = 'vertical';
                        textarea.style.minHeight = '100px';
                        textarea.style.overflowY = 'auto';
                        
                        // 添加拖动记忆功能
                        const storeKey = `ollamaTextareaSize_${nodeData.name}_${textarea.dataset.inputName}`;
                        
                        // 从本地存储读取高度
                        const savedHeight = localStorage.getItem(storeKey);
                        if (savedHeight) {
                            textarea.style.height = savedHeight + 'px';
                        }
                        
                        // 监听高度变化
                        textarea.addEventListener('mouseup', () => {
                            localStorage.setItem(storeKey, textarea.offsetHeight);
                        });
                    });
                }, 100);
            };
        }
    }
});