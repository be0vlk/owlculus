// Representative HTML supported by the pre-upgrade note schema.
export const richNote = `
<h1>Investigation</h1><h2>Evidence</h2><h3>Sources</h3>
<h4>Detail</h4><h5>Reference</h5><h6>Appendix</h6>
<p><strong>Bold</strong> <em>Italic</em> <u>Underline</u> <s>Strike</s>
<mark data-color="#ffe066" style="background-color: #ffe066">Yellow</mark>
<mark data-color="#74c0fc" style="background-color: #74c0fc">Blue</mark>
<a href="https://example.org/evidence" target="_blank" rel="noopener noreferrer">Source</a>
<code>inline()</code></p>
<ul><li><p>Bullet</p></li></ul><ol start="3"><li><p>Third</p></li></ol>
<ul data-type="taskList"><li data-type="taskItem" data-checked="true"><p>Reviewed</p>
<ul data-type="taskList"><li data-type="taskItem" data-checked="false"><p>Follow up</p></li></ul>
</li><li data-type="taskItem" data-checked="false"><p>Pending</p></li></ul>
<blockquote><p>Witness statement</p></blockquote>
<pre><code class="language-js">const evidence = 1;</code></pre><p>End of note</p>`
